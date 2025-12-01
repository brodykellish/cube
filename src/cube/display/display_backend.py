"""
Display backend abstraction for menu rendering.
Supports both pygame (development) and piomatter (LED cube).
"""

import numpy as np
import platform
from abc import ABC, abstractmethod
from typing import List


class DisplayBackend(ABC):
    """Abstract base class for display backends."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.framebuffer = np.zeros((height, width, 3), dtype=np.uint8)

    def compose_layers(self, layers: List[np.ndarray]) -> np.ndarray:
        """
        Composite multiple layers into a single framebuffer.

        Layers are composited bottom-to-top, with black pixels (0,0,0)
        in upper layers treated as transparent.

        Args:
            layers: List of framebuffers to composite (bottom to top)

        Returns:
            Composited framebuffer
        """
        if len(layers) == 0:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)

        if len(layers) == 1:
            return layers[0].copy()

        # Start with bottom layer
        result = layers[0].copy()

        # Overlay each subsequent layer
        for layer in layers[1:]:
            # Create mask: True where layer is non-black (has content)
            mask = np.any(layer != 0, axis=2, keepdims=True)

            # Apply layer pixels where mask is True
            result = np.where(mask, layer, result)

        return result

    def apply_corrections(self, framebuffer: np.ndarray, brightness: float = 100.0, gamma: float = 1.0) -> np.ndarray:
        """
        Apply brightness and gamma corrections to framebuffer.

        Args:
            framebuffer: Input framebuffer
            brightness: Brightness percentage (1-100)
            gamma: Gamma correction value (0.5-3.0)

        Returns:
            Corrected framebuffer
        """
        # Convert to float for processing
        result = framebuffer.astype(np.float32)

        # Apply gamma correction
        if gamma != 1.0:
            result = np.power(result / 255.0, gamma) * 255.0

        # Apply brightness scaling
        if brightness != 100.0:
            result = result * (brightness / 100.0)

        # Clamp to valid range and convert back to uint8
        result = np.clip(result, 0, 255).astype(np.uint8)

        return result

    @abstractmethod
    def show_framebuffer(self, framebuffer: np.ndarray):
        """
        Display a complete framebuffer.

        This method should handle all backend-specific display logic including:
        - Slicing for panel orientation
        - Re-indexing for cube layout
        - Window resizing (if applicable)

        Args:
            framebuffer: Complete framebuffer to display (any size)
        """
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
