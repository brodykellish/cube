"""
Visualization window wrapper for pyglet backend.

Provides a simple interface for visualization rendering and input handling.
Each window is responsible for handling its own events and input.
Must be created on main thread (macOS requirement), but OpenGL context is used in visualization thread.
"""
import numpy as np
from typing import Optional
from .pyglet_backend import PygletBackend
from ..input.input_manager import InputManager
from ..input.actions import InputContext


class VisualizationWindow:
    """Pyglet window wrapper for visualization rendering."""
    
    def __init__(self, width: int, height: int, scale: int = 1, title: str = "Cube Visualization", **kwargs):
        """
        Initialize visualization window.
        
        CRITICAL: Must be created on MAIN THREAD (macOS requirement)!
        The OpenGL context will be used in the visualization thread.
        
        Args:
            width: Window width in pixels
            height: Window height in pixels
            scale: Content scale factor
            title: Window title
            **kwargs: Additional arguments passed to PygletBackend
        """
        # Allow visualization window to be resizable so it can be moved to correct display
        kwargs.pop('resizable', None)  # Remove resizable if passed
        self.backend = PygletBackend(width, height, scale=scale, title=title, resizable=True, **kwargs)
        self.width = self.backend.width
        self.height = self.backend.height
        self._has_exit = False
        self._close_requested = False
        
        # Register close handler
        @self.backend.window.event
        def on_close():
            self._has_exit = True
        
        # Create and configure input manager for this window
        # Note: Input manager will be polled in visualization thread
        self.input_manager = InputManager()
        self.input_manager.set_context(InputContext.VISUALIZATION)
        
        # Register keyboard source (if available)
        if hasattr(self.backend, 'keyboard'):
            from cube.input.keyboard_source import KeyboardInputSource
            self.input_manager.register_source(
                KeyboardInputSource(self.backend.keyboard))
    
    def is_focused(self) -> bool:
        """
        Check if window has focus.
        
        Returns:
            True if window has focus
        """
        return not self._has_exit and self.backend.window.has_exit is False
    
    def poll(self) -> dict:
        """
        Poll pyglet events and return keyboard state.
        
        Returns:
            dict with keys: 'quit', 'key', 'keys', 'paste', 'mouse'
        """
        return self.backend.poll()
    
    def make_visible(self):
        """
        Make the window visible (must be called from main thread on macOS).
        
        This is safe to call from any thread, but window visibility changes
        are handled by pyglet's event system.
        """
        if not self.backend.window.visible:
            self.backend.window.set_visible(True)
    
    def display(self, framebuffer: np.ndarray):
        """
        Display visualization framebuffer.
        
        Args:
            framebuffer: RGB framebuffer (H, W, 3)
        """
        self.backend.display(framebuffer)
    
    def get_render_resolution(self) -> tuple[int, int]:
        """
        Get the shader rendering resolution.
        
        Returns:
            Tuple of (width, height) in pixels
        """
        return self.backend.get_render_resolution()
    
    def get_window_size(self) -> tuple[int, int]:
        """
        Get the window size (not framebuffer size).
        
        Returns:
            Tuple of (width, height) in pixels
        """
        return self.backend.get_window_size()
    
    def get_framebuffer_size(self) -> tuple[int, int]:
        """
        Get the framebuffer size (may differ from window size on HiDPI displays).
        
        Returns:
            Tuple of (width, height) in pixels
        """
        return self.backend.get_framebuffer_size()
    
    def set_fullscreen(self, fullscreen: bool):
        """
        Toggle fullscreen mode.
        
        Args:
            fullscreen: True to enter fullscreen, False to exit
        """
        self.backend.set_fullscreen(fullscreen)
    
    def close(self):
        """Request window close (thread-safe, actual close happens on main thread)."""
        self._close_requested = True
        self._has_exit = True
    
    def check_close_request(self):
        """Check if close was requested and close window (must be called from main thread)."""
        if self._close_requested:
            self._close_requested = False
            if hasattr(self.backend, 'window'):
                try:
                    self.backend.window.close()
                except Exception as e:
                    print(f"[VizWindow] Error closing window: {e}")
            return True
        return False
    
    def cleanup(self):
        """Clean up pyglet resources."""
        self.backend.close()

