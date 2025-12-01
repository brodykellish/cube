"""
Keyboard input abstraction.

Provides a unified interface for keyboard input across different platforms and input methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class KeyEvent:
    """Represents a single key press event."""

    def __init__(self, key: str):
        """
        Initialize a key event.

        Args:
            key: Normalized key name (e.g., 'up', 'down', 'enter', 'a', 'escape')
        """
        self.key = key

    def __repr__(self) -> str:
        return f"KeyEvent('{self.key}')"


class KeyboardState:
    """Represents the current state of keyboard input."""

    def __init__(self):
        """Initialize keyboard state."""
        self.quit = False
        self.key_press: Optional[str] = None  # Single key press this frame
        self.keys_held: List[str] = []  # All keys currently held down

    def __repr__(self) -> str:
        return f"KeyboardState(quit={self.quit}, key_press={self.key_press}, keys_held={self.keys_held})"


class Keyboard(ABC):
    """
    Abstract base class for keyboard input.

    Provides a unified interface for different keyboard input implementations:
    - PygameKeyboard: Uses pygame event system (for local macOS development)
    - SSHKeyboard: Reads terminal input over SSH (for remote RPi control)
    """

    @abstractmethod
    def poll(self) -> KeyboardState:
        """
        Poll for keyboard input and return current state.

        Returns:
            KeyboardState containing:
                - quit: Whether quit was requested (Ctrl+C, ESC+Q, etc.)
                - key_press: Single key that was pressed this frame (None if no press)
                - keys_held: List of all keys currently held down
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up resources and restore terminal state if needed."""
        pass


# Standard key name mappings used across all keyboard implementations
STANDARD_KEY_NAMES = {
    # Navigation
    'up', 'down', 'left', 'right',

    # Actions
    'enter', 'escape', 'back', 'quit',

    # Modifiers
    'shift', 'ctrl', 'alt',

    # Letters (for WASD, reload, etc.)
    'w', 'a', 's', 'd', 'r', 'e', 'c', 't', 'b',

    # Function keys
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',

    # Numbers
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',

    # Special
    'space', 'tab', 'backspace', 'delete',
}
