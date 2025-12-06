"""
Input handling for cube control system.

Provides keyboard input abstractions for different platforms:
- PygameKeyboard: For local macOS development using pygame events
- SSHKeyboard: For remote RPi control via SSH terminal input
- InputHandler: Unified interface for processing keyboard input
- GamepadCameraInput: Xbox controller / gamepad input for camera control
"""

from .keyboard import Keyboard, KeyboardState, KeyEvent
from .pygame_keyboard import PygameKeyboard
from .ssh_keyboard import SSHKeyboard
from .input_handler import InputHandler
from .gamepad import GamepadCameraInput, list_gamepads

__all__ = [
    'Keyboard',
    'KeyboardState',
    'KeyEvent',
    'PygameKeyboard',
    'SSHKeyboard',
    'InputHandler',
    'GamepadCameraInput',
    'list_gamepads',
]
