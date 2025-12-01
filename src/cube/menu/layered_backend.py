"""
Layered display backend with compositing support.

Provides multi-layer framebuffer system for overlaying UI elements
on top of shader visualizations or menu content.
"""

import numpy as np
from typing import List, Tuple, Optional
from .display_backend import create_display_backend, DisplayBackend


class LayeredDisplayBackend:
    """
    Multi-layer display backend with automatic composition.

    Supports multiple framebuffer layers that are composited together
    before being displayed. Useful for overlaying debug UI, menus, etc.
    on top of shader visualizations.

    Example:
        # Create display with 2 layers
        display = LayeredDisplayBackend(width=128, height=128, num_layers=2)

        # Layer 0: Base content (shader or menu)
        base_layer = display.get_layer(0)

        # Layer 1: Overlay (debug UI, FPS)
        overlay_layer = display.get_layer(1)

        # Render to layers
        base_layer[:] = shader_output
        overlay_layer[:] = render_debug_ui()

        # Display composited result
        display.show()
    """

    def __init__(self, width: int, height: int, num_layers: int = 2, opengl: bool = False, **kwargs):
        """
        Initialize layered display backend.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            num_layers: Number of framebuffer layers (default: 2)
            opengl: Enable OpenGL support for shader rendering
            **kwargs: Additional arguments passed to display backend
        """
        self.width = width
        self.height = height
        self.num_layers = num_layers
        self.opengl = opengl

        # Create underlying display backend with OpenGL support if requested
        self.backend = create_display_backend(width, height, opengl=opengl, **kwargs)

        # Create framebuffer layers
        # Layer 0: Base layer (opaque, always filled)
        # Layer 1+: Overlay layers (transparent where black)
        self.layers: List[np.ndarray] = []
        for i in range(num_layers):
            layer = np.zeros((height, width, 3), dtype=np.uint8)
            self.layers.append(layer)

        # Composition buffer
        self._composition_buffer = np.zeros((height, width, 3), dtype=np.uint8)

        print(f"Layered display initialized: {width}×{height} ({num_layers} layers)")

    def get_layer(self, index: int) -> np.ndarray:
        """
        Get framebuffer for specified layer.

        Args:
            index: Layer index (0 = base, 1+ = overlays)

        Returns:
            Numpy array of shape (height, width, 3), dtype=uint8
        """
        if index < 0 or index >= self.num_layers:
            raise IndexError(f"Layer index {index} out of range [0, {self.num_layers})")
        return self.layers[index]

    def clear_layer(self, index: int, color=(0, 0, 0)):
        """
        Clear specified layer to solid color.

        Args:
            index: Layer index
            color: RGB tuple (0-255)
        """
        self.layers[index][:, :] = color

    def clear_all_layers(self, color=(0, 0, 0)):
        """Clear all layers to solid color."""
        for layer in self.layers:
            layer[:, :] = color

    def compose_layers(self) -> np.ndarray:
        """
        Composite all layers into single framebuffer.

        Layer 0 is the opaque base layer. Subsequent layers are
        overlaid on top, with black pixels treated as transparent.

        Returns:
            Composited framebuffer (height, width, 3), dtype=uint8
        """
        # Start with base layer
        result = self.layers[0].copy()

        # Overlay additional layers
        for i in range(1, self.num_layers):
            layer = self.layers[i]

            # Create mask: True where layer is non-black (has content)
            mask = np.any(layer != 0, axis=2, keepdims=True)

            # Use layer pixels where mask is True, keep result pixels where False
            result = np.where(mask, layer, result)

        return result

    def show(self):
        """Composite all layers and display to hardware."""
        # Compose layers into composition buffer
        self._composition_buffer = self.compose_layers()

        # Copy to backend framebuffer
        self.backend.framebuffer[:, :] = self._composition_buffer

        # Display
        self.backend.show()

    def handle_events(self) -> dict:
        """
        Handle input events.

        Returns:
            dict with keys: 'quit' (bool), 'key' (str or None)
        """
        return self.backend.handle_events()

    def cleanup(self):
        """Clean up display resources."""
        self.backend.cleanup()

    @property
    def framebuffer(self) -> np.ndarray:
        """Get base layer framebuffer (for backward compatibility)."""
        return self.layers[0]
