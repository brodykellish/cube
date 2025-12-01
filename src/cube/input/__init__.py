"""
Input handling for cube control system.

Provides keyboard input abstractions for different platforms:
- PygameKeyboard: For local macOS development using pygame events
- SSHKeyboard: For remote RPi control via SSH terminal input
- InputHandler: Unified interface for processing keyboard input
"""

from .keyboard import Keyboard, KeyboardState, KeyEvent, STANDARD_KEY_NAMES
from .pygame_keyboard import PygameKeyboard
from .ssh_keyboard import SSHKeyboard
from .input_handler import InputHandler

__all__ = [
    'Keyboard',
    'KeyboardState',
    'KeyEvent',
    'PygameKeyboard',
    'SSHKeyboard',
    'InputHandler',
    'STANDARD_KEY_NAMES',
]
