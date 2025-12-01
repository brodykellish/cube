"""
Display backend abstraction for menu rendering.
Supports both pygame (development) and piomatter (LED cube).
"""

import numpy as np
import platform
from abc import ABC, abstractmethod


class DisplayBackend(ABC):
    """Abstract base class for display backends."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.framebuffer = np.zeros((height, width, 3), dtype=np.uint8)

    @abstractmethod
    def show(self):
        """Display the current framebuffer."""
        pass

    @abstractmethod
    def handle_events(self) -> dict:
        """
        Handle input events.

        Returns:
            dict with keys: 'quit' (bool), 'key' (str or None)
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up resources."""
        pass


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
                }
                result['key'] = key_map.get(event.key)

        return result

    def cleanup(self):
        """Clean up pygame."""
        self.pygame.quit()


class PiomatterBackend(DisplayBackend):
    """Piomatter backend for actual LED cube."""

    def __init__(self, width: int, height: int, **kwargs):
        super().__init__(width, height)

        import piomatter as piomatter

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

        # Create matrix
        self.matrix = piomatter.PioMatter(
            colorspace=piomatter.Colorspace.RGB888Packed,
            pinout=pinout,
            framebuffer=self.framebuffer,
            geometry=geometry
        )

        print(f"Piomatter backend initialized: {width}×{height}")

    def show(self):
        """Display framebuffer via piomatter."""
        self.matrix.show()

    def handle_events(self) -> dict:
        """
        Handle input events via GPIO buttons (if available).
        For now, returns no events - keyboard input would need GPIO button setup.
        """
        # TODO: Implement GPIO button handling for physical cube
        # This would read button states and map them to key events
        return {'quit': False, 'key': None}

    def cleanup(self):
        """Clean up piomatter resources."""
        # Piomatter handles cleanup automatically
        pass


def create_display_backend(width: int, height: int, preview: bool = False, **kwargs) -> DisplayBackend:
    """
    Factory function to create appropriate display backend.

    Args:
        width: Display width in pixels
        height: Display height in pixels
        preview: Force preview mode (pygame) even on RPi
        **kwargs: Additional backend-specific arguments

    Returns:
        DisplayBackend instance
    """
    # Determine which backend to use
    is_dev_platform = platform.system() in ('Darwin', 'Windows')
    use_preview = preview or is_dev_platform

    # Check for DRM device on Linux (indicates GPU available)
    has_drm = False
    if platform.system() == 'Linux' and not preview:
        import os
        has_drm = os.path.exists('/dev/dri/card0')

    if use_preview or not has_drm:
        # Use pygame for development
        scale = kwargs.get('scale', 1)
        return PygameBackend(width, height, scale=scale)
    else:
        # Use piomatter for LED cube
        return PiomatterBackend(width, height, **kwargs)
