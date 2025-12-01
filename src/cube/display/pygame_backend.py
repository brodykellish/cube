"""
Pygame display backend for development on macOS/Linux/Windows.
"""

import numpy as np
from .display_backend import DisplayBackend
from ..input.pygame_keyboard import PygameKeyboard


class PygameBackend(DisplayBackend):
    """Pygame backend for development on macOS/Linux/Windows."""

    def __init__(self, width: int, height: int, scale: int = 1, opengl: bool = False, **kwargs):
        """
        Initialize pygame backend.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            scale: Window scale factor (default 1)
            opengl: Enable OpenGL support (default False)
            **kwargs: Additional arguments (ignored, for cross-backend compatibility)
        """
        super().__init__(width, height)

        import pygame
        self.pygame = pygame

        pygame.init()
        self.scale = scale
        self.window_width = width * scale
        self.window_height = height * scale
        self.opengl = opengl

        # Create window with optional OpenGL support
        if opengl:
            from pygame.locals import DOUBLEBUF, OPENGL
            self.screen = pygame.display.set_mode(
                (self.window_width, self.window_height),
                DOUBLEBUF | OPENGL
            )
            print(f"Pygame OpenGL backend initialized: {self.window_width}×{self.window_height} (scale {scale}x)")
        else:
            self.screen = pygame.display.set_mode((self.window_width, self.window_height))
            print(f"Pygame backend initialized: {self.window_width}×{self.window_height} (scale {scale}x)")

        pygame.display.set_caption("Cube Control")

        # Initialize keyboard input handler
        self.keyboard = PygameKeyboard(pygame)

        # Track volumetric mode state
        self.volumetric_mode = False
        self.original_window_size = (self.window_width, self.window_height)

    def show(self):
        """Display framebuffer via pygame."""
        if self.opengl:
            # Render framebuffer using OpenGL
            from OpenGL.GL import (
                glDrawPixels, glRasterPos2i, GL_RGB, GL_UNSIGNED_BYTE,
                glPixelZoom, glClear, GL_COLOR_BUFFER_BIT
            )

            # Clear screen
            glClear(GL_COLOR_BUFFER_BIT)

            # Set raster position (bottom-left in OpenGL coords)
            glRasterPos2i(-1, -1)

            # Set pixel zoom for scaling
            glPixelZoom(self.scale, self.scale)

            # Flip framebuffer vertically for OpenGL coordinate system
            framebuffer_flipped = np.flip(self.framebuffer, axis=0)

            # Draw pixels
            glDrawPixels(
                self.framebuffer.shape[1],  # width
                self.framebuffer.shape[0],  # height
                GL_RGB,
                GL_UNSIGNED_BYTE,
                framebuffer_flipped
            )

            self.pygame.display.flip()
        else:
            # Convert numpy array to pygame surface
            surface = self.pygame.surfarray.make_surface(
                np.transpose(self.framebuffer, (1, 0, 2))
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
        """Handle pygame events using keyboard abstraction."""
        # Poll keyboard for input
        keyboard_state = self.keyboard.poll()

        # Convert KeyboardState to old dict format for backward compatibility
        result = {
            'quit': keyboard_state.quit,
            'key': keyboard_state.key_press,
            'keys': keyboard_state.keys_held
        }

        return result

    def show_volumetric(self, framebuffer: np.ndarray):
        """
        Display a volumetric framebuffer (resizes window to fit all panels).

        Args:
            framebuffer: Volumetric framebuffer (may be larger than normal display)
        """
        vol_height, vol_width = framebuffer.shape[:2]

        # Resize window if needed (only in non-OpenGL mode)
        if not self.opengl:
            desired_window_width = vol_width * self.scale
            desired_window_height = vol_height * self.scale

            # Only resize if different from current size
            if not self.volumetric_mode or (self.window_width, self.window_height) != (desired_window_width, desired_window_height):
                self.window_width = desired_window_width
                self.window_height = desired_window_height
                self.screen = self.pygame.display.set_mode((self.window_width, self.window_height))
                self.volumetric_mode = True
                print(f"Pygame window resized for volumetric mode: {self.window_width}×{self.window_height}")

        # Convert numpy array to pygame surface
        surface = self.pygame.surfarray.make_surface(
            np.transpose(framebuffer, (1, 0, 2))
        )

        # Scale up if needed
        if self.scale > 1:
            surface = self.pygame.transform.scale(
                surface,
                (vol_width * self.scale, vol_height * self.scale)
            )

        self.screen.blit(surface, (0, 0))
        self.pygame.display.flip()

    def exit_volumetric_mode(self):
        """Restore original window size after volumetric mode."""
        if self.volumetric_mode and not self.opengl:
            self.window_width, self.window_height = self.original_window_size
            self.screen = self.pygame.display.set_mode((self.window_width, self.window_height))
            self.volumetric_mode = False
            print(f"Pygame window restored: {self.window_width}×{self.window_height}")

    def cleanup(self):
        """Clean up pygame and keyboard."""
        self.keyboard.cleanup()
        self.pygame.quit()
