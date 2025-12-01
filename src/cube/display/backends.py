"""
Display backends for pygame and piomatter.

Backends receive composited framebuffers and handle the actual rendering
to screen or LED hardware.
"""

import numpy as np


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
        Handle input events via GPIO buttons (if available).

        For now, returns no events - keyboard input would need GPIO button setup.
        """
        # TODO: Implement GPIO button handling for physical cube
        return {'quit': False, 'key': None}

    def cleanup(self):
        """Clean up piomatter resources."""
        # Piomatter handles cleanup automatically
        pass
