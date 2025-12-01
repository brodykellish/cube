"""
Input handling for cube control system.

Provides keyboard input abstractions for different platforms:
- PygameKeyboard: For local macOS development using pygame events
- SSHKeyboard: For remote RPi control via SSH terminal input
"""

from .keyboard import Keyboard, KeyboardState, KeyEvent, STANDARD_KEY_NAMES
from .pygame_keyboard import PygameKeyboard
from .ssh_keyboard import SSHKeyboard

__all__ = [
    'Keyboard',
    'KeyboardState',
    'KeyEvent',
    'PygameKeyboard',
    'SSHKeyboard',
    'STANDARD_KEY_NAMES',
]
