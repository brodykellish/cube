"""
Pyglet keyboard input handler.

Provides unified keyboard state similar to PygameKeyboard.
"""

from typing import Optional, Set
from dataclasses import dataclass


@dataclass
class KeyboardState:
    """Keyboard state for a single frame."""
    quit: bool = False
    key_press: Optional[str] = None
    keys_held: Set[str] = None
    paste_text: Optional[str] = None


class PygletKeyboard:
    """
    Pyglet keyboard input handler.

    Converts pyglet events to unified keyboard state.
    """

    def __init__(self, window):
        """
        Initialize pyglet keyboard handler.

        Args:
            window: Pyglet window instance
        """
        self.window = window
        self.key_press_this_frame = None
        self.keys_held = set()
        self.paste_text = None
        self.quit_requested = False

        # Register event handlers
        @window.event
        def on_key_press(symbol, _):
            key_name = self._map_key(symbol)
            if key_name:
                self.key_press_this_frame = key_name
                self.keys_held.add(key_name)

            # Prevent default ESC behavior (closing window)
            # Return EVENT_HANDLED to stop propagation
            return True

        @window.event
        def on_key_release(symbol, _):
            key_name = self._map_key(symbol)
            if key_name and key_name in self.keys_held:
                self.keys_held.discard(key_name)

        @window.event
        def on_close():
            self.quit_requested = True

        @window.event
        def on_text(text):
            # Handle paste (Cmd+V / Ctrl+V)
            # Pyglet provides text input separately
            if text and len(text) > 1:  # Likely a paste
                self.paste_text = text

    def _map_key(self, symbol) -> Optional[str]:
        """Map pyglet key symbol to key name."""
        import pyglet.window.key as key

        # Special keys and punctuation (normalized to a stable logical name).
        # This keeps press/release symmetric and makes shift-compounding robust
        # across different keyboard layouts. Use the pyglet.window.key enum
        # directly for clarity.
        key_map = {
            # Control / navigation
            key.ESCAPE: 'escape',
            key.ENTER: 'enter',
            key.RETURN: 'enter',
            key.TAB: 'tab',
            key.BACKSPACE: 'back',
            key.SPACE: 'space',
            key.UP: 'up',
            key.DOWN: 'down',
            key.LEFT: 'left',
            key.RIGHT: 'right',

            # Modifiers
            key.LSHIFT: 'shift',
            key.RSHIFT: 'shift',
        }

        unshifted_punctuation_map = {
            # Primary punctuation row (base logical names)
            key.BACKSLASH: '\\',
            key.MINUS: '-',
            key.EQUAL: '=',
            key.BRACKETLEFT: '[',
            key.BRACKETRIGHT: ']',
            key.SEMICOLON: ';',
            key.APOSTROPHE: "'",
            key.COMMA: ',',
            key.PERIOD: '.',
            key.SLASH: '/',
        }

        shifted_punctuation_map = {
            # Primary punctuation row (base logical names)
            key.BAR: '\\',
            key.UNDERSCORE: '-',
            key.PLUS: '=',
            key.BRACELEFT: '[',
            key.BRACERIGHT: ']',
            key.COLON: ';',
            key.DOUBLEQUOTE: "'",
            key.LESS: ',',
            key.GREATER: '.',
            key.QUESTION: '/',
        }

        shifted_number_map = {
            key.PARENRIGHT: '0',
            key.EXCLAMATION: '1',
            key.AT: '2',
            key.HASH: '3',
            key.DOLLAR: '4',
            key.PERCENT: '5',
            key.ASCIICIRCUM: '6',
            key.AMPERSAND: '7',
            key.ASTERISK: '8',
            key.PARENLEFT: '9',
        }

        key_map = {**key_map, **unshifted_punctuation_map,
                   **shifted_punctuation_map, **shifted_number_map}

        if symbol in key_map:
            return key_map[symbol]

        # Letter keys (a-z)
        if key.A <= symbol <= key.Z:
            return chr(symbol).lower()

        # Number keys (0-9)
        if key._0 <= symbol <= key._9:
            return chr(symbol - key._0 + ord('0'))

        return None

    def poll(self) -> KeyboardState:
        """
        Get current keyboard state for this frame.

        Returns:
            KeyboardState with current frame's input
        """
        state = KeyboardState(
            quit=self.quit_requested,
            key_press=self.key_press_this_frame,
            keys_held=self.keys_held.copy(),
            paste_text=self.paste_text
        )

        # Reset frame-specific state
        self.key_press_this_frame = None
        self.paste_text = None

        return state

    def cleanup(self):
        """Clean up resources."""
        pass
