"""
Pygame display backend for development on macOS/Linux/Windows.
"""

import numpy as np
from .display_backend import DisplayBackend
from ..input.pygame_keyboard import PygameKeyboard


class PygameBackend(DisplayBackend):
    """Pygame backend for development on macOS/Linux/Windows."""

    def __init__(self, width: int, height: int, scale: int = 1, **kwargs):
        """
        Initialize pygame backend.

        Args:
            width: Window width in pixels (fixed)
            height: Window height in pixels (fixed)
            scale: Content scale factor - determines internal rendering resolution (default 1)
                   scale=2 means render at width/2 × height/2 and scale up to fit window
            **kwargs: Additional arguments (ignored, for cross-backend compatibility)
        """
        # Internal rendering resolution (scaled down)
        internal_width = width // scale
        internal_height = height // scale
        super().__init__(internal_width, internal_height)

        import pygame
        self.pygame = pygame

        pygame.init()
        self.scale = scale
        self.window_width = width
        self.window_height = height

        # Create window
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        print(f"Pygame backend initialized: {self.window_width}×{self.window_height} window, {internal_width}×{internal_height} render (scale {scale}x)")

        pygame.display.set_caption("Cube Control")

        # Initialize keyboard input handler
        self.keyboard = PygameKeyboard(pygame)
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.mouse_button_pressed = False

    def show_framebuffer(self, framebuffer: np.ndarray):
        """
        Display a complete framebuffer via pygame.

        Scales framebuffer content to fill the fixed window size.
        Uses nearest-neighbor scaling to preserve sharp pixel edges.

        Args:
            framebuffer: Complete framebuffer to display (any size)
        """
        # Convert numpy array to pygame surface
        surface = self.pygame.surfarray.make_surface(
            np.transpose(framebuffer, (1, 0, 2))
        )

        # Scale content to fill window using nearest-neighbor (no smoothing)
        # This preserves sharp pixel edges for that "chunky pixel" look
        surface = self.pygame.transform.scale(
            surface,
            (self.window_width, self.window_height)
        )

        self.screen.blit(surface, (0, 0))
        self.pygame.display.flip()

    def handle_events(self) -> dict:
        """Handle pygame events using keyboard abstraction."""
        # Poll keyboard for input
        keyboard_state = self.keyboard.poll()
        
        # Get mouse state
        mouse_pos = self.pygame.mouse.get_pos()
        mouse_buttons = self.pygame.mouse.get_pressed()
        scale_x = self.width / self.window_width if self.window_width > 0 else 1.0
        scale_y = self.height / self.window_height if self.window_height > 0 else 1.0
        self.mouse_x = float(mouse_pos[0] * scale_x)
        self.mouse_y = float((self.window_height - mouse_pos[1]) * scale_y)
        self.mouse_button_pressed = mouse_buttons[0] or mouse_buttons[1] or mouse_buttons[2]

        # Convert KeyboardState to dict format
        result = {
            'quit': keyboard_state.quit,
            'key': keyboard_state.key_press,
            'keys': keyboard_state.keys_held,
            'paste': keyboard_state.paste_text,
            'mouse': {
                'x': self.mouse_x,
                'y': self.mouse_y,
                'button_pressed': self.mouse_button_pressed
            }
        }

        return result

    def cleanup(self):
        """Clean up pygame and keyboard."""
        self.keyboard.cleanup()
        self.pygame.quit()
