"""
SSH keyboard implementation.

Reads keyboard input from terminal over SSH - suitable for remote control of RPi.
"""

import sys
import termios
import tty
import fcntl
import os
from typing import Optional
from .keyboard import Keyboard, KeyboardState


class SSHKeyboard(Keyboard):
    """
    Keyboard implementation using terminal input (termios).

    This is used for remote SSH sessions where we need to read raw terminal input.
    Typically used on Raspberry Pi to accept keyboard input from a remote Mac via SSH.
    """

    def __init__(self):
        """Initialize SSH keyboard with terminal in raw/cbreak mode."""
        self.stdin_fd = sys.stdin.fileno()
        self.old_settings = None
        self.old_flags = None
        self._setup_terminal()

        # Track held keys (since terminal input doesn't provide key-up events)
        # We'll use a simplified model: keys are "held" for one frame after press
        self._held_keys = set()

    def _setup_terminal(self):
        """Set up terminal in cbreak mode for non-blocking character input."""
        try:
            # Save old terminal settings
            self.old_settings = termios.tcgetattr(sys.stdin)
            self.old_flags = fcntl.fcntl(self.stdin_fd, fcntl.F_GETFL)

            # Use cbreak mode (allows Ctrl-C) instead of raw mode
            tty.setcbreak(self.stdin_fd)

            # Make stdin non-blocking
            fcntl.fcntl(self.stdin_fd, fcntl.F_SETFL, self.old_flags | os.O_NONBLOCK)
        except Exception as e:
            print(f"Warning: Could not setup terminal for keyboard input: {e}")

    def _read_terminal_input(self) -> Optional[str]:
        """
        Read available input from terminal (non-blocking).

        Returns:
            String of all characters read, or None if no input available
        """
        chars = ''
        try:
            while True:
                try:
                    c = sys.stdin.read(1)
                    if c:
                        chars += c
                    else:
                        break
                except (IOError, OSError):
                    break
        except Exception:
            pass

        return chars if chars else None

    def _parse_terminal_input(self, chars: str) -> Optional[str]:
        """
        Parse raw terminal input into standard key names.

        Args:
            chars: Raw characters from terminal

        Returns:
            Standard key name, or None if not recognized
        """
        # Check for Ctrl-C
        if '\x03' in chars:
            return 'quit'

        # Check for escape sequences (arrow keys)
        # Full escape sequences
        if '\x1b[A' in chars:
            return 'up'
        elif '\x1b[B' in chars:
            return 'down'
        elif '\x1b[C' in chars:
            return 'right'
        elif '\x1b[D' in chars:
            return 'left'

        # Partial escape sequences (ESC consumed by terminal)
        elif '[A' in chars:
            return 'up'
        elif '[B' in chars:
            return 'down'
        elif '[C' in chars:
            return 'right'
        elif '[D' in chars:
            return 'left'

        # Single character keys
        # WASD navigation
        if chars == 'w':
            return 'w'
        elif chars == 's':
            return 's'
        elif chars == 'a':
            return 'a'
        elif chars == 'd':
            return 'd'

        # Special keys
        elif chars == '\r' or chars == '\n':
            return 'enter'
        elif chars == ' ':
            return 'space'
        elif chars == '\x1b':  # Bare ESC
            return 'escape'
        elif chars == '\x7f':  # Backspace
            return 'backspace'

        # Letter keys
        elif chars == 'b':
            return 'b'
        elif chars == 'q':
            return 'q'
        elif chars == 'r':
            return 'r'
        elif chars == 'e':
            return 'e'
        elif chars == 'c':
            return 'c'
        elif chars == 't':
            return 't'

        # Number keys
        elif chars in '0123456789':
            return chars

        return None

    def poll(self) -> KeyboardState:
        """
        Poll terminal for keyboard input.

        Returns:
            KeyboardState with current keyboard state
        """
        state = KeyboardState()

        # Read input from terminal
        chars = self._read_terminal_input()

        if chars:
            # Parse into standard key name
            key = self._parse_terminal_input(chars)

            if key:
                state.key_press = key

                # Handle quit signal
                if key in ('quit', 'q') and chars == '\x03':
                    state.quit = True

                # For SSH keyboard, we simulate "held" keys by keeping them
                # in the held list for this frame
                self._held_keys.add(key)

        # Copy held keys to state
        state.keys_held = list(self._held_keys)

        # Clear held keys for next frame
        # (Terminal input doesn't give us key-up events, so we can't truly
        # track held keys. This gives a one-frame "hold" effect)
        self._held_keys.clear()

        return state

    def cleanup(self):
        """Restore terminal to original settings."""
        if self.old_settings is not None:
            try:
                # Restore stdin flags
                if self.old_flags is not None:
                    fcntl.fcntl(self.stdin_fd, fcntl.F_SETFL, self.old_flags)

                # Restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except Exception as e:
                print(f"Warning: Could not restore terminal settings: {e}")
