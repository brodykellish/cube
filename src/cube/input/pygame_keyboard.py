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
        """
        Build mapping from pygame key constants to standard key names.

        Note: This only maps special keys (arrows, function keys, etc.).
        Printable characters will be passed through via event.unicode.
        """
        return {
            # Arrow keys
            self.pygame.K_UP: 'up',
            self.pygame.K_DOWN: 'down',
            self.pygame.K_LEFT: 'left',
            self.pygame.K_RIGHT: 'right',

            # Action keys
            self.pygame.K_RETURN: 'enter',
            self.pygame.K_ESCAPE: 'escape',
            self.pygame.K_BACKSPACE: 'backspace',
            self.pygame.K_DELETE: 'delete',
            self.pygame.K_TAB: 'tab',

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
                # Check for modifier keys
                mods = self.pygame.key.get_mods()

                # Check for Ctrl+C (clear input)
                if (mods & self.pygame.KMOD_CTRL) and event.key == self.pygame.K_c:
                    state.key_press = 'ctrl-c'
                    continue

                # Check for Cmd+V (macOS) or Ctrl+V (Windows/Linux) - paste
                is_cmd = mods & self.pygame.KMOD_META  # Command on macOS
                is_ctrl = mods & self.pygame.KMOD_CTRL  # Ctrl on Windows/Linux

                if (is_cmd or is_ctrl) and event.key == self.pygame.K_v:
                    # Get clipboard text using platform-specific method
                    clipboard_text = None

                    try:
                        # Try platform-specific clipboard access first
                        import sys
                        import subprocess

                        if sys.platform == 'darwin':
                            # macOS - use pbpaste command (pygame.scrap doesn't work well)
                            result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=1)
                            if result.returncode == 0:
                                clipboard_text = result.stdout
                        elif sys.platform in ('linux', 'linux2'):
                            # Linux - try xclip or xsel
                            try:
                                result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'],
                                                      capture_output=True, text=True, timeout=1)
                                if result.returncode == 0:
                                    clipboard_text = result.stdout
                            except FileNotFoundError:
                                # xclip not available, try xsel
                                try:
                                    result = subprocess.run(['xsel', '--clipboard', '--output'],
                                                          capture_output=True, text=True, timeout=1)
                                    if result.returncode == 0:
                                        clipboard_text = result.stdout
                                except FileNotFoundError:
                                    pass

                        # Fallback to pygame.scrap on Windows or if commands fail
                        if clipboard_text is None:
                            # Initialize scrap module if needed
                            if not self.pygame.scrap.get_init():
                                self.pygame.scrap.init()

                            # Get text from clipboard
                            clipboard_bytes = self.pygame.scrap.get(self.pygame.SCRAP_TEXT)
                            if clipboard_bytes:
                                if isinstance(clipboard_bytes, bytes):
                                    clipboard_text = clipboard_bytes.decode('utf-8', errors='ignore')
                                else:
                                    clipboard_text = clipboard_bytes

                        # Clean up clipboard text
                        if clipboard_text:
                            clipboard_text = clipboard_text.rstrip('\x00').strip()
                            if clipboard_text:
                                state.paste_text = clipboard_text

                    except Exception as e:
                        print(f"Paste error: {e}")
                    continue

                # First try to get a mapped key (for special keys like arrows, escape, etc.)
                mapped_key = self._key_map.get(event.key)

                if mapped_key:
                    # Store mapped key (arrow keys, escape, enter, etc.)
                    state.key_press = mapped_key
                elif event.unicode and event.unicode.isprintable():
                    # Pass through any printable character (letters, numbers, symbols)
                    # This allows full text input without needing to map every key
                    state.key_press = event.unicode

                # Note: Non-printable characters without a mapping are ignored

        # Get all currently held keys
        pressed = self.pygame.key.get_pressed()
        for pygame_key, key_name in self._key_map.items():
            if pressed[pygame_key]:
                state.keys_held.append(key_name)

        return state

    def cleanup(self):
        """Clean up pygame keyboard (no cleanup needed)."""
        pass
