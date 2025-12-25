"""
Menu window wrapper for pygame backend.

Provides a simple interface for menu rendering and input handling.
Each window is responsible for handling its own events and input.
"""
import numpy as np
from typing import Optional
from .pygame_backend import PygameBackend
from ..input.input_manager import InputManager
from ..input.actions import InputContext


class MenuWindow:
    """Pygame window wrapper for menu UI."""
    
    def __init__(self, width: int, height: int, scale: int = 1, **kwargs):
        """
        Initialize menu window.
        
        Args:
            width: Window width in pixels
            height: Window height in pixels
            scale: Content scale factor
            **kwargs: Additional arguments passed to PygameBackend
        """
        self.backend = PygameBackend(width, height, scale=scale, **kwargs)
        self.width = self.backend.width
        self.height = self.backend.height
        
        # Create and configure input manager for this window
        self.input_manager = InputManager()
        self.input_manager.set_context(InputContext.MENU)
        
        # Register keyboard source
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
        # Check if pygame window has focus
        return self.backend.pygame.mouse.get_focused() or self.backend.pygame.key.get_focused()
    
    def process_events(self) -> dict:
        """
        Process window events and update input manager.
        
        This method handles all event processing for the menu window:
        - Polls pygame events
        - Updates input manager if window is focused
        - Returns event information
        
        Returns:
            dict with keys: 'quit' (bool), and other event data
        """
        # Poll pygame events
        events = self.backend.handle_events()
        
        # Update input manager if window is focused
        if self.is_focused():
            self.input_manager.poll()
        
        return events
    
    def handle_events(self) -> dict:
        """
        Poll pygame events and return keyboard state.
        
        DEPRECATED: Use process_events() instead.
        Kept for backwards compatibility.
        
        Returns:
            dict with keys: 'quit', 'key', 'keys', 'paste', 'mouse'
        """
        return self.backend.handle_events()
    
    def show_framebuffer(self, framebuffer: np.ndarray):
        """
        Display menu framebuffer.
        
        Args:
            framebuffer: RGB framebuffer (H, W, 3)
        """
        self.backend.show_framebuffer(framebuffer)
    
    def cleanup(self):
        """Clean up pygame resources."""
        self.backend.cleanup()

