"""
Unified display interface for LED cube control system.

Provides a clean API for multi-layer framebuffer compositing and rendering
to various backends (pygame, piomatter).
"""
import numpy as np
import platform
from typing import List
from .display_backend import create_display_backend, PygletDisplayBackend


class Display:
    """
    Multi-layer display with backend abstraction.

    Renderers write to individual layers, the Display handles compositing
    and delegates final rendering to the appropriate backend.
    """

    def __init__(self, width: int, height: int, num_layers: int=1, backend=None, backend_type: str='auto', **kwargs):
        """
        Initialize display.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            num_layers: Number of framebuffer layers (default 1)
            backend: Optional backend instance to reuse (if None, creates one)
            backend_type: Backend type ('auto', 'pygame', 'piomatter') - only used if backend is None
            **kwargs: Additional backend-specific arguments (only used if backend is None)
        """
        self.window_width = width
        self.window_height = height
        self.num_layers = num_layers
        
        if backend is not None:
            # Reuse provided backend instance
            self.backend = backend
            self.backend_type = getattr(backend, 'backend_type', 'unknown')
        else:
            # Create new backend (for Pi mode or standalone usage)
            if backend_type == 'auto':
                backend_type = self._detect_backend(**kwargs)
            
            self.backend_type = backend_type
            print(f"Creating backend: {backend_type}")
            print(f"Width: {width}, Height: {height}, kwargs: {kwargs}")
            self.backend = self._create_backend(backend_type, width, height, **kwargs)
            print(f"Backend created: {self.backend}")

        # Use backend's actual framebuffer dimensions (may be scaled)
        self.width = self.backend.width
        self.height = self.backend.height
        
        self.layers = []
        for i in range(num_layers):
            layer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            self.layers.append(layer)
        
        print(f'Display initialized: {self.width}×{self.height} render, {width}×{height} window ({backend} backend, {num_layers} layers)')

    def _detect_backend(self, **kwargs) -> str:
        """
        Auto-detect appropriate backend based on platform.

        Returns:
            'pygame' for development platforms, 'piomatter' for RPi with hardware
        """
        is_dev_platform = platform.system() in ('Darwin', 'Windows')
        if is_dev_platform:
            return 'pygame'
        
        if platform.system() == 'Linux':
            import os
            has_drm = os.path.exists('/dev/dri/card0')
            if not has_drm:
                return 'pygame'
        
        return 'piomatter'

    def _create_backend(self, backend: str, width: int, height: int, **kwargs):
        """
        Create backend instance.

        Args:
            backend: Backend type ('pygame' or 'piomatter')
            width: Display width
            height: Display height
            **kwargs: Backend-specific arguments

        Returns:
            Backend instance
        """
        if backend == 'pygame':
            from .pygame_backend import PygameBackend
            return PygameBackend(width, height, **kwargs)
        if backend == 'piomatter':
            from .piomatter_backend import PiomatterBackend
            return PiomatterBackend(width, height, **kwargs)
        if backend == 'pyglet':
            return PygletDisplayBackend(width, height, **kwargs)
            raise ValueError(f'Unknown backend type: {backend}')

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
            raise IndexError(f'Layer index {index} out of range [0, {self.num_layers})')
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
            raise IndexError(f'Layer index {index} out of range [0, {self.num_layers})')
        if framebuffer.shape != (self.height, self.width, 3):
            raise ValueError(f"Framebuffer shape {framebuffer.shape} doesn't match expected ({self.height}, {self.width}, 3)")
        self.layers[index][:, :] = framebuffer

    def show(self, brightness: float=100.0, gamma: float=1.0):
        """
        Composite layers and display to screen.

        This is the main display method that should be called each frame.
        Backend handles all compositing and display-specific logic.

        Args:
            brightness: Brightness percentage (1-100), default 100
            gamma: Gamma correction value (0.5-3.0), default 1.0
        """
        framebuffer = self.backend.compose_layers(self.layers)
        framebuffer = self.backend.apply_corrections(framebuffer, brightness, gamma)
        self.backend.show_framebuffer(framebuffer)

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
