"""
Pygame display backend for development on macOS/Linux/Windows.
"""

import numpy as np
from .display_backend import DisplayBackend


class PygameBackend(DisplayBackend):
    """Pygame backend for development on macOS/Linux/Windows."""

    def __init__(self, width: int, height: int, scale: int = 1, opengl: bool = False):
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
        """Handle pygame events."""
        result = {'quit': False, 'key': None, 'keys': []}

        # Process events (quit, etc.)
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
                    self.pygame.K_e: 'e',
                    self.pygame.K_c: 'c',
                    self.pygame.K_t: 't',
                }
                mapped_key = key_map.get(event.key)
                if mapped_key:
                    result['key'] = mapped_key  # For backward compatibility

        # Check currently held keys for continuous input
        pressed = self.pygame.key.get_pressed()
        key_map = {
            self.pygame.K_UP: 'up',
            self.pygame.K_DOWN: 'down',
            self.pygame.K_LEFT: 'left',
            self.pygame.K_RIGHT: 'right',
            self.pygame.K_w: 'w',
            self.pygame.K_s: 's',
            self.pygame.K_a: 'a',
            self.pygame.K_d: 'd',
            self.pygame.K_e: 'e',
            self.pygame.K_c: 'c',
            self.pygame.K_LSHIFT: 'shift',
            self.pygame.K_RSHIFT: 'shift',
        }

        keys_held = []
        for pygame_key, key_name in key_map.items():
            if pressed[pygame_key]:
                if key_name not in keys_held:
                    keys_held.append(key_name)

        result['keys'] = keys_held

        return result

    def cleanup(self):
        """Clean up pygame."""
        self.pygame.quit()
