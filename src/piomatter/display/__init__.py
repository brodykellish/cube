"""
Display module for LED cube control system.

Provides a clean, self-contained API for rendering framebuffers to either
pygame (development) or piomatter (LED hardware). Handles multiple layers,
compositing, and backend selection.
"""

from .display import Display

__all__ = ['Display']
