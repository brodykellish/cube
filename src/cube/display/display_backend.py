# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/display/display_backend.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-23 05:44:34 UTC (1766468674)

"""
Display backend abstraction for menu rendering.

Supports both pygame (development) and piomatter (LED cube).
"""
import numpy as np
import platform
from abc import ABC, abstractmethod
from typing import List

from .backend import create_backend


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
        result = layers[0].copy()
        for layer in layers[1:]:
            mask = np.any(layer != 0, axis=2, keepdims=True)
            result = np.where(mask, layer, result)
        return result

    def apply_corrections(self, framebuffer: np.ndarray, brightness: float=100.0, gamma: float=1.0) -> np.ndarray:
        """
        Apply brightness and gamma corrections to framebuffer.

        Args:
            framebuffer: Input framebuffer
            brightness: Brightness percentage (1-100)
            gamma: Gamma correction value (0.5-3.0)

        Returns:
            Corrected framebuffer
        """
        result = framebuffer.astype(np.float32)
        if gamma != 1.0:
            result = np.power(result / 255.0, gamma) * 255.0
        if brightness != 100.0:
            result = result * (brightness / 100.0)
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
        return

    @abstractmethod
    def handle_events(self) -> dict:
        """
        Handle input events.

        Returns:
            dict with keys: 'quit' (bool), 'key' (str or None)
        """
        return

    @abstractmethod
    def cleanup(self):
        """Clean up resources."""
        return


class PygletDisplayBackend(DisplayBackend):
    """
    Adapter that wraps the legacy pyglet backend so it can be used
    with the higher-level Display interface.
    """

    def __init__(self, width: int, height: int, scale: int = 1, **kwargs):
        backend = create_backend("pyglet", width, height, scale=scale, **kwargs)
        super().__init__(backend.width, backend.height)
        # Underlying legacy backend (provides window + keyboard, etc.)
        self._backend = backend
        # Expose keyboard driver for higher-level input wiring.
        self.keyboard = getattr(backend, "keyboard", None)

    def show_framebuffer(self, framebuffer: np.ndarray):
        """Display a complete framebuffer via pyglet backend."""
        self._backend.display(framebuffer)

    def handle_events(self) -> dict:
        """Delegate to pyglet backend event polling."""
        return self._backend.poll()

    def cleanup(self):
        """Clean up pyglet backend resources."""
        self._backend.close()

def create_display_backend(width: int, height: int, preview: bool=False, **kwargs) -> DisplayBackend:
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
    is_dev_platform = platform.system() in ('Darwin', 'Windows')
    use_preview = preview or is_dev_platform
    has_drm = False
    if platform.system() == 'Linux' and (not preview):
        import os
        has_drm = os.path.exists('/dev/dri/card0')
    if not use_preview and (not has_drm):
        from .pygame_backend import PygameBackend
        scale = kwargs.get('scale', 1)
        return PygameBackend(width, height, scale=scale)
    from .piomatter_backend import PiomatterBackend
    return PiomatterBackend(width, height, **kwargs)