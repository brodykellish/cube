"""
Uniform source abstraction for shader uniforms.

Provides a clean interface for different types of uniform sources:
- Mouse input (MouseUniformSource)
- Camera (CameraUniformSource)
- Audio mapping (AudioUniformMappingSource)
- Video (VideoUniformSource)

Each uniform source updates its own set of shader uniforms independently.
"""
import time
from abc import ABC, abstractmethod
from typing import Dict, Any


class UniformSource(ABC):
    """
    Abstract base class for uniform sources.

    Uniform sources provide shader uniforms that update in real-time.
    Each source is independent and can be combined with others.
    """

    @abstractmethod
    def update(self, dt: float):
        """
        Update internal state based on elapsed time.

        Args:
            dt: Delta time since last update (seconds)
        """
        return

    @abstractmethod
    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get current uniform values.

        Returns:
            Dictionary mapping uniform name -> value
            Values can be: float, int, tuple (for vectors), numpy arrays
        """
        return

    @abstractmethod
    def cleanup(self):
        """Clean up resources (close files, devices, etc.)."""
        return

    def reset(self):
        """Reset input source to initial state (optional)."""
        return


class MouseUniformSource(UniformSource):
    """
    Mouse input source.
    
    Provides iMouse uniform (vec4) following Shadertoy format:
    - iMouse.xy: Current mouse position in pixels
    - iMouse.zw: Mouse position when button was clicked (or 0 if not clicked)
    """
    
    def __init__(self, width: int = 1, height: int = 1):
        """
        Initialize mouse input source.
        
        Args:
            width: Render width (for coordinate normalization)
            height: Render height (for coordinate normalization)
        """
        self.width = width
        self.height = height
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.click_x = 0.0
        self.click_y = 0.0
        self.button_pressed = False
    
    def set_mouse_position(self, x: float, y: float):
        """
        Update current mouse position.
        
        Args:
            x: Mouse x position in pixels
            y: Mouse y position in pixels
        """
        self.mouse_x = x
        self.mouse_y = y
    
    def set_mouse_button(self, pressed: bool):
        """
        Update mouse button state.
        
        Args:
            pressed: True if button is pressed, False if released
        """
        if pressed and not self.button_pressed:
            self.click_x = self.mouse_x
            self.click_y = self.mouse_y
        elif not pressed:
            self.click_x = 0.0
            self.click_y = 0.0
        self.button_pressed = pressed
    
    def set_resolution(self, width: int, height: int):
        """
        Update render resolution (for coordinate scaling if needed).
        
        Args:
            width: Render width
            height: Render height
        """
        self.width = width
        self.height = height
    
    def update(self, dt: float):
        """Update mouse input (no-op, state updated via set_mouse_position/set_mouse_button)."""
        return
    
    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get mouse input as iMouse uniform.
        
        Returns:
            {'iMouse': (x, y, click_x, click_y)}
        """
        return {'iMouse': (self.mouse_x, self.mouse_y, self.click_x, self.click_y)}
    
    def cleanup(self):
        """No cleanup needed for mouse input."""
        return
    
    def reset(self):
        """Reset mouse state to initial position."""
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.click_x = 0.0
        self.click_y = 0.0
        self.button_pressed = False


class UniformSourceManager:
    """
    Manages multiple uniform sources and combines their uniforms.

    Allows multiple uniform sources to coexist (e.g., mouse + camera + audio).
    Each source updates independently and provides its own uniforms.
    """

    def __init__(self):
        """Initialize uniform source manager."""
        self.sources = []

    def add_source(self, source: UniformSource):
        """
        Add a uniform source.

        Args:
            source: Uniform source to add
        """
        self.sources.append(source)

    def remove_source(self, source: UniformSource):
        """
        Remove a uniform source.

        Args:
            source: Uniform source to remove
        """
        if source in self.sources:
            source.cleanup()
            self.sources.remove(source)

    def update(self, dt: float):
        """
        Update all uniform sources.

        Args:
            dt: Delta time since last update
        """
        for source in self.sources:
            source.update(dt)

    def get_all_uniforms(self) -> Dict[str, Any]:
        """
        Get combined uniforms from all sources.

        If multiple sources provide the same uniform, the last one wins.

        Returns:
            Combined dictionary of all uniforms
        """
        uniforms = {}
        for source in self.sources:
            uniforms.update(source.get_uniforms())
        return uniforms

    def cleanup(self):
        """Clean up all uniform sources."""
        for source in self.sources:
            source.cleanup()
        self.sources.clear()

    def reset_all(self):
        """Reset all uniform sources to initial state."""
        for source in self.sources:
            source.reset()
