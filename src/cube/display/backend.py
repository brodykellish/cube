# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/display/backend.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-16 18:16:45 UTC (1765909005)

"""
Backend abstraction for display system.

Minimal interface: backends only need display(), poll(), close().
"""
from abc import ABC, abstractmethod
import numpy as np

class Backend(ABC):
    """Minimal backend interface - just display, poll, close"""

    @property
    @abstractmethod
    def width(self) -> int:
        """Current render width in pixels"""
        return

    @property
    @abstractmethod
    def height(self) -> int:
        """Current render height in pixels"""
        return

    @abstractmethod
    def display(self, framebuffer: np.ndarray):
        """
        Display RGB framebuffer.

        Args:
            framebuffer: RGB framebuffer (H, W, 3) uint8
        """
        return

    @abstractmethod
    def poll(self) -> dict:
        """
        Poll events.

        Returns:
            dict with keys:
                - 'quit': bool (True if quit requested)
                - 'key': str or None (key name if key pressed)
                - 'keys': set (currently held keys)
                - 'paste': str or None (pasted text if any)
        """
        return

    @abstractmethod
    def was_resized(self) -> bool:
        """
        Check if window was resized since last check.

        Returns:
            True if resized (clears flag)
        """
        return

    @abstractmethod
    def close(self):
        """Cleanup resources"""
        return
pass

def create_backend(backend: str, width: int, height: int, scale: int=1, **kwargs) -> Backend:
    """
    Factory function for creating backends.

    Args:
        backend: Backend type ('pyglet' or 'piomatter')
        width: Window width in pixels
        height: Window height in pixels
        scale: Render scale factor (default 1)
        **kwargs: Backend-specific arguments

    Returns:
        Backend instance
    """
    if backend == 'pyglet':
        from .pyglet_backend import PygletBackend
        return PygletBackend(width, height, scale, **kwargs)
    if backend == 'piomatter':
        from .piomatter_backend import PiomatterBackend
        return PiomatterBackend(width, height, **kwargs)
    raise ValueError(f'Unknown backend: {backend}')

def apply_corrections(fb: np.ndarray, brightness: float, gamma: float) -> np.ndarray:
    """
    Apply brightness and gamma correction (pure function).

    Args:
        fb: Input framebuffer
        brightness: Brightness percentage (1-100)
        gamma: Gamma correction value (0.5-3.0)

    Returns:
        Corrected framebuffer
    """
    if brightness == 100.0 and gamma == 1.0:
        return fb
    result = fb.astype(np.float32)
    if gamma != 1.0:
        result = np.power(result / 255.0, gamma) * 255.0
    if brightness != 100.0:
        result *= brightness / 100.0
    return np.clip(result, 0, 255).astype(np.uint8)

class Compositor:
    """Composites layers with black-as-transparent rule"""

    def composite(self, layers: list) -> np.ndarray:
        """
        Composite multiple layers bottom-to-top.

        Black pixels (0,0,0) in upper layers are treated as transparent.

        Args:
            layers: List of framebuffers (bottom to top)

        Returns:
            Composited framebuffer
        """
        if len(layers) == 0:
            raise ValueError('No layers to composite')
        if len(layers) == 1:
            return layers[0].copy()
        result = layers[0].copy()
        for layer in layers[1:]:
            mask = np.any(layer != 0, axis=2, keepdims=True)
            result = np.where(mask, layer, result)
        return result