"""
Input handler - unified interface for processing keyboard input.

Provides a clean, decoupled way to handle both discrete key presses (menus)
and continuous key holds (shaders) using the same basic approach.
"""

from typing import Optional, List, Any


class InputHandler:
    """
    Unified input handler that wraps keyboard state from display backend.

    Provides clean methods for checking key presses and held keys,
    decoupling input logic from the controller.
    """

    def __init__(self):
        """Initialize input handler."""
        self.quit_requested = False
        self.key_pressed: Optional[str] = None
        self.keys_held: List[str] = []

    def update(self, events: dict):
        """
        Update input state from display backend events.

        Args:
            events: Events dict from display.handle_events()
                    Format: {'quit': bool, 'key': str|None, 'keys': list}
        """
        self.quit_requested = events.get('quit', False)
        self.key_pressed = events.get('key')
        self.keys_held = events.get('keys', [])

    def is_quit_requested(self) -> bool:
        """Check if quit was requested (Ctrl+C, window close, etc.)."""
        return self.quit_requested

    def is_key_pressed(self, *keys: str) -> bool:
        """
        Check if any of the given keys was pressed this frame.

        Args:
            *keys: Key names to check (e.g., 'enter', 'escape', 'up')

        Returns:
            True if any of the keys was pressed

        Example:
            if input.is_key_pressed('enter', 'space'):
                select_item()
        """
        return self.key_pressed in keys if self.key_pressed else False

    def is_exit_requested(self) -> bool:
        """
        Check if user requested to exit current mode.

        Returns:
            True if escape, quit, or back was pressed
        """
        return self.is_key_pressed('escape', 'quit', 'back')

    def is_key_held(self, *keys: str) -> bool:
        """
        Check if any of the given keys is currently held down.

        Args:
            *keys: Key names to check

        Returns:
            True if any of the keys is held down

        Example:
            if input.is_key_held('w', 'up'):
                move_forward()
        """
        return any(key in self.keys_held for key in keys)

    def get_pressed_key(self) -> Optional[str]:
        """
        Get the key that was pressed this frame.

        Returns:
            Key name or None if no key was pressed
        """
        return self.key_pressed

    def get_held_keys(self) -> List[str]:
        """
        Get list of all keys currently held down.

        Returns:
            List of held key names
        """
        return self.keys_held.copy()

    def apply_to_shader_keyboard(self, shader_keyboard: Any, shift_pressed_attr: str = None) -> dict:
        """
        Apply held keys to a shader's KeyboardInput object.

        This provides a standard mapping from held keys to shader camera controls.

        Args:
            shader_keyboard: The shader's KeyboardInput instance
            shift_pressed_attr: Optional attribute name to set shift state on parent object

        Returns:
            Dict with mapped states for external use if needed

        Example:
            # In shader mode:
            input.apply_to_shader_keyboard(
                shader_renderer.keyboard_input,
                shift_pressed_attr='shift_pressed'
            )
        """
        # Standard directional mapping (supports both arrow keys and WASD)
        shader_keyboard.set_key_state('up', self.is_key_held('up', 'w'))
        shader_keyboard.set_key_state('down', self.is_key_held('down', 's'))
        shader_keyboard.set_key_state('left', self.is_key_held('left', 'a'))
        shader_keyboard.set_key_state('right', self.is_key_held('right', 'd'))

        # Return mapped states
        return {
            'up': self.is_key_held('up', 'w'),
            'down': self.is_key_held('down', 's'),
            'left': self.is_key_held('left', 'a'),
            'right': self.is_key_held('right', 'd'),
            'shift': self.is_key_held('shift'),
        }

    def __repr__(self) -> str:
        return (
            f"InputHandler(quit={self.quit_requested}, "
            f"key_pressed={self.key_pressed}, "
            f"keys_held={self.keys_held})"
        )
