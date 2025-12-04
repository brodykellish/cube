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
        self.paste_text: Optional[str] = None  # Clipboard text pasted this frame (Cmd+V / Ctrl+V)

    def __repr__(self) -> str:
        return f"KeyboardState(quit={self.quit}, key_press={self.key_press}, keys_held={self.keys_held}, paste={self.paste_text})"


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
