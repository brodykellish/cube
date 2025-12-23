"""
Signal system for cube_v2.

Signals are continuous streams that can be sampled at any time.
They represent inputs like keyboard, audio, MIDI, or LFOs.
"""

from abc import ABC, abstractmethod
from typing import Optional
import math


class Signal(ABC):
    """
    Base class for all signals.
    
    Signals can be sampled at any time to get their current value.
    """
    
    @abstractmethod
    def sample(self, t: float) -> float:
        """
        Sample the signal at time t.
        
        Args:
            t: Current time in seconds
            
        Returns:
            Signal value (typically 0.0 to 1.0, but can vary)
        """
        pass


class KeyboardSignal(Signal):
    """
    Signal that represents a keyboard key press.
    
    Returns 1.0 when key is pressed, 0.0 when released.
    """
    
    def __init__(self, key: str):
        """
        Initialize keyboard signal.
        
        Args:
            key: Key identifier (e.g., "space", "a", "1")
        """
        self.key = key
        self.pressed = False
    
    def sample(self, t: float) -> float:
        """Return 1.0 if pressed, 0.0 otherwise."""
        return 1.0 if self.pressed else 0.0
    
    def set_pressed(self, pressed: bool):
        """Update the pressed state."""
        self.pressed = pressed


class LFO(Signal):
    """
    Low-frequency oscillator signal.
    
    Generates a sine wave oscillation.
    """
    
    def __init__(self, frequency: float = 1.0, phase: float = 0.0):
        """
        Initialize LFO.
        
        Args:
            frequency: Oscillation frequency in Hz
            phase: Initial phase offset in radians
        """
        self.frequency = frequency
        self.phase = phase
    
    def sample(self, t: float) -> float:
        """
        Sample LFO as sine wave.
        
        Returns value in range [-1.0, 1.0]
        """
        return math.sin(2.0 * math.pi * self.frequency * t + self.phase)
    
    def sample_normalized(self, t: float) -> float:
        """
        Sample LFO normalized to [0.0, 1.0].
        
        Returns value in range [0.0, 1.0]
        """
        return (self.sample(t) + 1.0) / 2.0

