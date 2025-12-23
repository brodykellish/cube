"""
Keyboard input source wrapper.

Wraps existing keyboard drivers (PygletKeyboard, SSHKeyboard, etc.)
and adapts them to the InputSource interface.
"""
from typing import Set
from .input_source import InputSource, InputState

class KeyboardInputSource(InputSource):
    """
    Wraps keyboard drivers to InputSource interface.

    Supports PygletKeyboard, SSHKeyboard, and other keyboard drivers
    that implement the poll() → KeyboardState interface.
    Outputs uniform key format: 'key:KEYNAME'
    """

    def __init__(self, keyboard_driver, priority: int=10):
        """
        Initialize keyboard input source.

        Args:
            keyboard_driver: Keyboard driver (PygletKeyboard, etc.)
            priority: Priority for conflict resolution (default: 10)
        """
        self.keyboard = keyboard_driver
        self._priority = priority
        self._last_held = set()

    @property
    def name(self) -> str:
        """Source name"""
        return 'keyboard'

    @property
    def priority(self) -> int:
        """Priority for conflict resolution"""
        return self._priority

    def poll(self) -> InputState:
        """
        Poll keyboard and convert to InputState.

        Returns:
            InputState with keyboard events in uniform key format: 'key:KEYNAME'
        """
        kb_state = self.keyboard.poll()
        held = {f'key:{k}' for k in kb_state.keys_held}
        pressed = held - self._last_held
        released = self._last_held - held
        self._last_held = held.copy()
        
        return InputState(
            source_name=self.name,
            source_priority=self.priority,
            pressed=pressed,
            released=released,
            held=held,
            axes={},
            quit_requested=kb_state.quit,
            paste_text=kb_state.paste_text
        )

    def is_available(self) -> bool:
        """Keyboard is always available"""
        return True

    def cleanup(self):
        """Clean up keyboard resources"""
        self.keyboard.cleanup()