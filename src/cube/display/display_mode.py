"""
Display Mode Abstraction - Single vs Multi-Window.

Provides unified interface for:
- SingleWindowMode: Current 3-layer composite system
- MultiWindowMode: Three separate windows (main viz, menu, debug)
"""
from abc import ABC, abstractmethod
import numpy as np
from typing import Tuple


class DisplayMode(ABC):
    """Abstract interface for display modes."""

    @abstractmethod
    def show_visualization(self, framebuffer: np.ndarray, brightness: float, gamma: float):
        """Display visualization framebuffer."""
        pass

    @abstractmethod
    def show_menu(self, menu_layer: np.ndarray):
        """Display menu interface."""
        pass

    @abstractmethod
    def show_debug(self, debug_layer: np.ndarray):
        """Display debug overlay/window."""
        pass

    @abstractmethod
    def handle_events(self) -> dict:
        """
        Process window events.

        Returns:
            dict with keys: 'quit' (bool), 'key' (str or None)
        """
        pass

    @abstractmethod
    def get_dimensions(self) -> Tuple[int, int]:
        """Get render dimensions (width, height)."""
        pass

    @abstractmethod
    def is_menu_focused(self) -> bool:
        """Check if menu has focus (routes input to menu vs visualization)."""
        pass

    @abstractmethod
    def toggle_debug_window(self):
        """Toggle debug window visibility."""
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up display resources."""
        pass
