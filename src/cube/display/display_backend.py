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

    def show_volumetric(self, framebuffer: np.ndarray):
        """
        Display a volumetric framebuffer (may be larger than normal display size).

        This is an optional method for backends that support dynamic window resizing.
        Default implementation crops to fit the normal framebuffer.

        Args:
            framebuffer: Volumetric framebuffer to display (may be any size)
        """
        # Default: crop to fit normal framebuffer
        h = min(framebuffer.shape[0], self.height)
        w = min(framebuffer.shape[1], self.width)
        self.framebuffer[:h, :w] = framebuffer[:h, :w]
        self.show()


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
        from .pygame_backend import PygameBackend
        scale = kwargs.get('scale', 1)
        return PygameBackend(width, height, scale=scale)
    else:
        # Use piomatter for LED cube
        from .piomatter_backend import PiomatterBackend
        return PiomatterBackend(width, height, **kwargs)
