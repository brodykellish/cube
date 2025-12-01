"""
Pygame keyboard implementation.

Uses pygame's event system for keyboard input - suitable for local development on macOS.
"""

from typing import Any, Dict
from .keyboard import Keyboard, KeyboardState


class PygameKeyboard(Keyboard):
    """
    Keyboard implementation using pygame events.

    This is used for local macOS development where pygame can directly
    capture keyboard events from the OS.
    """

    def __init__(self, pygame: Any):
        """
        Initialize pygame keyboard.

        Args:
            pygame: The pygame module (passed in to avoid import issues)
        """
        self.pygame = pygame
        self._key_map = self._build_key_map()

    def _build_key_map(self) -> Dict[int, str]:
        """Build mapping from pygame key constants to standard key names."""
        return {
            # Arrow keys
            self.pygame.K_UP: 'up',
            self.pygame.K_DOWN: 'down',
            self.pygame.K_LEFT: 'left',
            self.pygame.K_RIGHT: 'right',

            # WASD (mapped to same directional names as arrows)
            self.pygame.K_w: 'w',
            self.pygame.K_a: 'a',
            self.pygame.K_s: 's',
            self.pygame.K_d: 'd',

            # Action keys
            self.pygame.K_RETURN: 'enter',
            self.pygame.K_SPACE: 'space',
            self.pygame.K_ESCAPE: 'escape',
            self.pygame.K_BACKSPACE: 'backspace',
            self.pygame.K_DELETE: 'delete',
            self.pygame.K_TAB: 'tab',

            # Letter keys
            self.pygame.K_b: 'b',  # back
            self.pygame.K_q: 'q',  # quit
            self.pygame.K_r: 'r',  # reload
            self.pygame.K_e: 'e',  # forward (camera)
            self.pygame.K_c: 'c',  # backward (camera)
            self.pygame.K_t: 't',  # toggle
            self.pygame.K_m: 'm',  # mixer

            # Modifiers
            self.pygame.K_LSHIFT: 'shift',
            self.pygame.K_RSHIFT: 'shift',
            self.pygame.K_LCTRL: 'ctrl',
            self.pygame.K_RCTRL: 'ctrl',
            self.pygame.K_LALT: 'alt',
            self.pygame.K_RALT: 'alt',

            # Function keys
            self.pygame.K_F1: 'f1',
            self.pygame.K_F2: 'f2',
            self.pygame.K_F3: 'f3',
            self.pygame.K_F4: 'f4',
            self.pygame.K_F5: 'f5',
            self.pygame.K_F6: 'f6',
            self.pygame.K_F7: 'f7',
            self.pygame.K_F8: 'f8',
            self.pygame.K_F9: 'f9',
            self.pygame.K_F10: 'f10',
            self.pygame.K_F11: 'f11',
            self.pygame.K_F12: 'f12',

            # Number keys
            self.pygame.K_0: '0',
            self.pygame.K_1: '1',
            self.pygame.K_2: '2',
            self.pygame.K_3: '3',
            self.pygame.K_4: '4',
            self.pygame.K_5: '5',
            self.pygame.K_6: '6',
            self.pygame.K_7: '7',
            self.pygame.K_8: '8',
            self.pygame.K_9: '9',
        }

    def poll(self) -> KeyboardState:
        """
        Poll pygame for keyboard input.

        Returns:
            KeyboardState with current keyboard state
        """
        state = KeyboardState()

        # Process events for single key presses
        for event in self.pygame.event.get():
            if event.type == self.pygame.QUIT:
                state.quit = True
            elif event.type == self.pygame.KEYDOWN:
                mapped_key = self._key_map.get(event.key)
                if mapped_key:
                    # Store single key press (only the most recent if multiple)
                    state.key_press = mapped_key

                    # Special handling for quit keys
                    if mapped_key in ('escape', 'q'):
                        # ESC or Q can signal quit in some contexts
                        pass

        # Get all currently held keys
        pressed = self.pygame.key.get_pressed()
        for pygame_key, key_name in self._key_map.items():
            if pressed[pygame_key]:
                state.keys_held.append(key_name)

        return state

    def cleanup(self):
        """Clean up pygame keyboard (no cleanup needed)."""
        pass
