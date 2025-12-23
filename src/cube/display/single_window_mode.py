"""
Single Window Display Mode - Current system.

Three-layer composite in single window (Raspberry Pi compatible).
"""
import numpy as np
from typing import Tuple
from .display_mode import DisplayMode
from .display import Display


class SingleWindowMode(DisplayMode):
    """
    Single window with 3-layer compositing.

    Layer 0: Menu
    Layer 1: Shader/Visualization
    Layer 2: Debug overlay

    Compatible with current system and Raspberry Pi.
    """

    def __init__(self, width: int, height: int, scale: int=1, **kwargs):
        """
        Initialize single window mode.

        Args:
            width: Display width
            height: Display height
            **kwargs: Passed to Display backend
        """
        print(f'Initializing SingleWindowMode with width: {width}, height: {height}, kwargs: {kwargs}')
        self.display = Display(width, height, scale=scale, num_layers=3, **kwargs)
        print(f'Display initialized: {self.display.width}×{self.display.height}')
        
        self.width = self.display.width
        self.height = self.display.height
        self.menu_layer = self.display.get_layer(0)
        self.shader_layer = self.display.get_layer(1)
        self.debug_layer = self.display.get_layer(2)
        self.debug_visible = True
        self.menu_active = True

    def show_visualization(self, framebuffer: np.ndarray, brightness: float, gamma: float):
        """Copy framebuffer to shader layer and display."""
        fb_height, fb_width = framebuffer.shape[:2]
        layer_height, layer_width = self.shader_layer.shape[:2]
        
        if fb_height == layer_height and fb_width == layer_width:
            self.shader_layer[:] = framebuffer
        else:
            self.shader_layer[:, :, :] = 0
            y_offset = (layer_height - fb_height) // 2
            x_offset = (layer_width - fb_width) // 2
            self.shader_layer[y_offset:y_offset + fb_height, x_offset:x_offset + fb_width] = framebuffer
        
        self.display.show(brightness=brightness, gamma=gamma)

    def show_menu(self, menu_layer: np.ndarray):
        """Menu is always part of composite (layer 0)."""
        pass

    def show_debug(self, debug_layer: np.ndarray):
        """Debug is always part of composite (layer 2)."""
        pass

    def handle_events(self) -> dict:
        """Handle events from single window."""
        return self.display.handle_events()

    def get_dimensions(self) -> Tuple[int, int]:
        """Get display dimensions."""
        return (self.width, self.height)

    def is_menu_focused(self) -> bool:
        """In single window mode, menu is 'focused' when we're not visualizing."""
        return self.menu_active

    def set_menu_active(self, active: bool):
        """Set whether menu is active (controller calls this)."""
        self.menu_active = active

    def toggle_debug_window(self):
        """Toggle debug visibility (in single mode, just controls rendering)."""
        self.debug_visible = not self.debug_visible

    def is_debug_visible(self) -> bool:
        """Check if debug should be rendered."""
        return self.debug_visible

    def cleanup(self):
        """Clean up display."""
        self.display.cleanup()
