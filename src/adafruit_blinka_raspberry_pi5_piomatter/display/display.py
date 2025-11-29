"""
Unified display interface for LED cube control system.

Provides a clean API for multi-layer framebuffer compositing and rendering
to various backends (pygame, piomatter).
"""

import numpy as np
import platform
from typing import List

from .backends import create_backend


class Display:
    """
    Multi-layer display with backend abstraction.

    Renderers write to individual layers, the Display handles compositing
    and delegates final rendering to the appropriate backend.
    """

    def __init__(
        self,
        width: int,
        height: int,
        num_layers: int = 1,
        backend: str = 'auto',
        **kwargs
    ):
        """
        Initialize display.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            num_layers: Number of framebuffer layers (default 1)
            backend: Backend type ('auto', 'pygame', 'piomatter')
            **kwargs: Additional backend-specific arguments
        """
        self.width = width
        self.height = height
        self.num_layers = num_layers

        # Create framebuffer layers
        self.layers: List[np.ndarray] = []
        for i in range(num_layers):
            layer = np.zeros((height, width, 3), dtype=np.uint8)
            self.layers.append(layer)

        # Select and initialize backend
        if backend == 'auto':
            backend = self._detect_backend(**kwargs)

        self.backend_type = backend
        self.backend = create_backend(backend, width, height, **kwargs)

        print(f"Display initialized: {width}×{height} ({backend} backend, {num_layers} layers)")

    def _detect_backend(self, **kwargs) -> str:
        """
        Auto-detect appropriate backend based on platform.

        Returns:
            'pygame' for development platforms, 'piomatter' for RPi with hardware
        """
        is_dev_platform = platform.system() in ('Darwin', 'Windows')
        preview = kwargs.get('preview', False)

        if preview or is_dev_platform:
            return 'pygame'

        # Check for DRM device on Linux (indicates GPU available)
        if platform.system() == 'Linux':
            import os
            has_drm = os.path.exists('/dev/dri/card0')
            if not has_drm:
                return 'pygame'

        return 'piomatter'

    def get_layer(self, index: int) -> np.ndarray:
        """
        Get a layer framebuffer for rendering.

        Renderers can write directly to this layer array.

        Args:
            index: Layer index (0 = bottom, higher = on top)

        Returns:
            Numpy array of shape (height, width, 3) with dtype uint8
        """
        if index < 0 or index >= self.num_layers:
            raise IndexError(f"Layer index {index} out of range [0, {self.num_layers})")
        return self.layers[index]

    def set_layer(self, index: int, framebuffer: np.ndarray):
        """
        Set a layer from a framebuffer.

        Alternative to writing directly to get_layer().

        Args:
            index: Layer index
            framebuffer: Numpy array of shape (height, width, 3)
        """
        if index < 0 or index >= self.num_layers:
            raise IndexError(f"Layer index {index} out of range [0, {self.num_layers})")

        if framebuffer.shape != (self.height, self.width, 3):
            raise ValueError(
                f"Framebuffer shape {framebuffer.shape} doesn't match "
                f"expected ({self.height}, {self.width}, 3)"
            )

        self.layers[index][:, :] = framebuffer

    def compose_layers(self) -> np.ndarray:
        """
        Composite all layers into a single framebuffer.

        Layers are composited bottom-to-top, with black pixels (0,0,0)
        in upper layers treated as transparent.

        Returns:
            Composited framebuffer of shape (height, width, 3)
        """
        if self.num_layers == 1:
            return self.layers[0].copy()

        # Start with bottom layer
        result = self.layers[0].copy()

        # Overlay each subsequent layer
        for i in range(1, self.num_layers):
            layer = self.layers[i]

            # Create mask: True where layer is non-black (has content)
            mask = np.any(layer != 0, axis=2, keepdims=True)

            # Apply layer pixels where mask is True
            result = np.where(mask, layer, result)

        return result

    def show(self):
        """
        Composite layers and display to screen.

        This is the main display method that should be called each frame.
        """
        # Composite all layers
        framebuffer = self.compose_layers()

        # Display via backend
        self.backend.show(framebuffer)

    def handle_events(self) -> dict:
        """
        Handle input events.

        Returns:
            dict with keys:
                - 'quit': bool (True if quit requested)
                - 'key': str or None (key name if key pressed)
        """
        return self.backend.handle_events()

    def cleanup(self):
        """Clean up display resources."""
        self.backend.cleanup()
