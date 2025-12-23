"""
Input source abstraction for unified input system.

All input devices (keyboard, MIDI, gamepad) implement the InputSource interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Set, Dict, Optional, Union

@dataclass
class InputState:
    """
    Raw input state from a source for one frame.

    Contains discrete inputs (key presses, MIDI notes) and
    continuous inputs (MIDI CCs, analog sticks).
    """
    source_name: str
    source_priority: int
    pressed: Set[str] = field(default_factory=set)
    released: Set[str] = field(default_factory=set)
    held: Set[str] = field(default_factory=set)
    axes: Dict[str, float] = field(default_factory=dict)
    quit_requested: bool = False
    paste_text: Optional[str] = None

class InputSource(ABC):
    """
    Abstract base class for input devices.

    All input sources (keyboard, MIDI, gamepad) implement this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Source identifier.

        Returns:
            String like 'keyboard', 'midi', 'gamepad'
        """
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Priority for conflict resolution.

        Higher priority wins when multiple sources
        provide values for the same axis.

        Typical values:
            MIDI: 100 (highest - physical controller)
            Gamepad: 50 (medium)
            Keyboard: 10 (lowest - fallback)

        Returns:
            Priority value
        """
        pass

    @abstractmethod
    def poll(self) -> InputState:
        """
        Poll input device and return current frame state.

        Returns:
            InputState with all active inputs
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if input device is connected/available.

        Returns:
            True if device can be polled
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up device resources"""
        pass