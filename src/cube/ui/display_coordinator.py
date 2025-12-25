"""
Display coordinator for menu window layer composition and display.

Handles compositing menu, shader, and debug layers and displaying them.
"""
import numpy as np
from typing import Optional
from cube.display.menu_window import MenuWindow


class DisplayCoordinator:
    """
    Coordinates display of multiple layers in the menu window.
    
    Handles:
    - Layer composition (menu, shader, debug)
    - Brightness/gamma corrections
    - Display to window
    """
    
    def __init__(
        self,
        menu_window: MenuWindow,
        settings: dict,
    ):
        """
        Initialize display coordinator.
        
        Args:
            menu_window: MenuWindow instance to display to
            settings: Settings dict with brightness/gamma values
        """
        self.menu_window = menu_window
        self.settings = settings
    
    def display(
        self,
        menu_layer: np.ndarray,
        shader_layer: np.ndarray,
        debug_layer: np.ndarray,
        preview_layer: np.ndarray,
    ) -> None:
        """
        Composite layers and display to menu window.
        
        Args:
            menu_layer: Menu UI layer
            shader_layer: Shader visualization layer
            debug_layer: Debug overlay layer
            preview_layer: Preview window layer (bottom-right corner)
        """
        # Composite layers (bottom to top: menu, shader, debug, preview)
        layers = [menu_layer, shader_layer, debug_layer, preview_layer]
        composite = self.menu_window.backend.compose_layers(layers)
        
        # Apply corrections
        composite = self.menu_window.backend.apply_corrections(
            composite,
            self.settings.get('brightness', 90.0),
            self.settings.get('gamma', 1.0)
        )
        
        # Display
        self.menu_window.show_framebuffer(composite)

