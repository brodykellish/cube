"""
Display backends for pygame and piomatter.

Backends receive composited framebuffers and handle the actual rendering
to screen or LED hardware.
"""

import numpy as np
import sys
import select
import termios
import tty


def create_backend(backend_type: str, width: int, height: int, **kwargs):
    """
    Factory function to create display backend.

    Args:
        backend_type: 'pygame' or 'piomatter'
        width: Display width
        height: Display height
        **kwargs: Backend-specific arguments

    Returns:
        Backend instance
    """
    if backend_type == 'pygame':
        return PygameBackend(width, height, **kwargs)
    elif backend_type == 'piomatter':
        return PiomatterBackend(width, height, **kwargs)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


class PygameBackend:
    """Pygame backend for development on macOS/Linux/Windows."""

    def __init__(self, width: int, height: int, scale: int = 1, **kwargs):
        """
        Initialize pygame backend.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            scale: Window scale factor (default 1)
        """
        import pygame
        self.pygame = pygame

        pygame.init()
        self.width = width
        self.height = height
        self.scale = scale
        self.window_width = width * scale
        self.window_height = height * scale

        # Create window in regular mode (never use OpenGL mode)
        self.screen = self.pygame.display.set_mode((self.window_width, self.window_height))
        self.pygame.display.set_caption("Cube Control")
        print(f"Pygame backend: {self.window_width}×{self.window_height} (scale {self.scale}x)")

    def show(self, framebuffer: np.ndarray):
        """
        Display framebuffer using regular pygame blitting.

        Args:
            framebuffer: Numpy array of shape (height, width, 3)
        """
        # Convert numpy array to pygame surface
        surface = self.pygame.surfarray.make_surface(
            np.transpose(framebuffer, (1, 0, 2))
        )

        # Scale up if needed
        if self.scale > 1:
            surface = self.pygame.transform.scale(
                surface,
                (self.window_width, self.window_height)
            )

        self.screen.blit(surface, (0, 0))
        self.pygame.display.flip()

    def handle_events(self) -> dict:
        """Handle pygame events."""
        result = {'quit': False, 'key': None}

        for event in self.pygame.event.get():
            if event.type == self.pygame.QUIT:
                result['quit'] = True
            elif event.type == self.pygame.KEYDOWN:
                # Map pygame keys to simple key names
                key_map = {
                    self.pygame.K_UP: 'up',
                    self.pygame.K_DOWN: 'down',
                    self.pygame.K_LEFT: 'left',
                    self.pygame.K_RIGHT: 'right',
                    self.pygame.K_RETURN: 'enter',
                    self.pygame.K_SPACE: 'enter',
                    self.pygame.K_ESCAPE: 'escape',
                    self.pygame.K_q: 'quit',
                    self.pygame.K_b: 'back',
                    self.pygame.K_w: 'up',
                    self.pygame.K_s: 'down',
                    self.pygame.K_a: 'left',
                    self.pygame.K_d: 'right',
                    self.pygame.K_r: 'reload',
                    self.pygame.K_t: 't',
                }
                result['key'] = key_map.get(event.key)

        return result

    def cleanup(self):
        """Clean up pygame."""
        self.pygame.quit()


class PiomatterBackend:
    """Piomatter backend for actual LED cube."""

    def __init__(self, width: int, height: int, **kwargs):
        """
        Initialize piomatter backend.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            **kwargs: Piomatter-specific arguments (pinout, num_planes, etc.)
        """
        import piomatter

        if not piomatter._PIOMATTER_AVAILABLE:
            raise RuntimeError(
                "piomatter C extension is not available. "
                "Make sure you're running on a Raspberry Pi 5 and the extension is built correctly."
            )

        self.width = width
        self.height = height

        # Setup terminal for raw input (non-blocking keyboard)
        self.old_terminal_settings = None
        try:
            self.old_terminal_settings = termios.tcgetattr(sys.stdin)
            # Use cbreak mode to allow Ctrl-C to work
            tty.setcbreak(sys.stdin.fileno())

            # Make stdin non-blocking
            import fcntl
            import os
            self.stdin_fd = sys.stdin.fileno()
            self.old_stdin_flags = fcntl.fcntl(self.stdin_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.stdin_fd, fcntl.F_SETFL, self.old_stdin_flags | os.O_NONBLOCK)
            print("\n" + "=" * 60)
            print("KEYBOARD CONTROLS (via SSH)")
            print("=" * 60)
            print("Navigation: w/s (↑/↓) or arrow keys")
            print("Select:     Enter or Space")
            print("Back:       b (ESC not available over SSH)")
            print("Quit:       q")
            print("=" * 60 + "\n")
        except (termios.error, AttributeError):
            # Not a terminal (e.g., running in background)
            pass

        # Extract piomatter-specific arguments
        pinout_name = kwargs.get('pinout', 'AdafruitMatrixBonnet')
        pinout = getattr(piomatter.Pinout, pinout_name)

        # Create geometry
        geometry = piomatter.Geometry(
            width=width,
            height=height,
            n_planes=kwargs.get('num_planes', 10),
            n_addr_lines=kwargs.get('num_address_lines', 4),
            n_temporal_planes=kwargs.get('num_temporal_planes', 0),
            rotation=piomatter.Orientation.Normal,
            serpentine=kwargs.get('serpentine', True)
        )

        # Create internal framebuffer
        self.framebuffer = np.zeros((height, width, 3), dtype=np.uint8)

        # Create matrix
        self.matrix = piomatter.PioMatter(
            colorspace=piomatter.Colorspace.RGB888Packed,
            pinout=pinout,
            framebuffer=self.framebuffer,
            geometry=geometry
        )

        print(f"Piomatter backend: {width}×{height}")

    def show(self, framebuffer: np.ndarray):
        """
        Display framebuffer.

        Args:
            framebuffer: Numpy array of shape (height, width, 3)
        """
        # Copy to internal framebuffer
        self.framebuffer[:, :] = framebuffer
        # Display
        self.matrix.show()

    def handle_events(self) -> dict:
        """
        Handle input events from stdin (keyboard over SSH).
        Uses non-blocking read to get keyboard input without blocking the render loop.
        """
        result = {'quit': False, 'key': None}

        try:
            # Try to read all available input (non-blocking)
            chars = ''
            while True:
                try:
                    c = sys.stdin.read(1)
                    if c:
                        chars += c
                    else:
                        break
                except (IOError, OSError):
                    # No more data available
                    break

            if not chars:
                return result

            print(f"[DEBUG] Read chars: {repr(chars)}")

            # Map single characters to key events
            key_map = {
                'w': 'up',
                'W': 'up',
                's': 'down',
                'S': 'down',
                'a': 'left',
                'A': 'left',
                'd': 'right',
                'D': 'right',
                '\r': 'enter',
                '\n': 'enter',
                ' ': 'enter',
                'b': 'back',
                'B': 'back',
                'q': 'quit',
                'Q': 'quit',
                '\x03': 'quit',  # Ctrl-C
            }

            # Check for escape sequences (arrow keys)
            if '\x1b[A' in chars:
                result['key'] = 'up'
            elif '\x1b[B' in chars:
                result['key'] = 'down'
            elif '\x1b[C' in chars:
                result['key'] = 'right'
            elif '\x1b[D' in chars:
                result['key'] = 'left'
            # Check for standalone [ followed by direction (ESC consumed by terminal)
            elif '[A' in chars:
                result['key'] = 'up'
            elif '[B' in chars:
                result['key'] = 'down'
            elif '[C' in chars:
                result['key'] = 'right'
            elif '[D' in chars:
                result['key'] = 'left'
            # Check for regular keys
            elif len(chars) == 1:
                result['key'] = key_map.get(chars)

        except Exception as e:
            print(f"[DEBUG] Unexpected error in handle_events: {e}")
            import traceback
            traceback.print_exc()

        if result['key']:
            print(f"[DEBUG] Key detected: {result['key']}")
        return result

    def cleanup(self):
        """Clean up piomatter resources and restore terminal."""
        # Restore stdin flags
        if hasattr(self, 'old_stdin_flags'):
            try:
                import fcntl
                fcntl.fcntl(self.stdin_fd, fcntl.F_SETFL, self.old_stdin_flags)
            except:
                pass

        # Restore terminal settings
        if self.old_terminal_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_terminal_settings)
            except (termios.error, AttributeError):
                pass
