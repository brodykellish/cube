# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/input/ssh_keyboard.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-23 05:44:34 UTC (1766468674)

"""
SSH keyboard implementation.

Reads keyboard input from a terminal (typically over SSH) and normalizes it
into the same key names used by the pygame keyboard implementation.
"""
import sys
import termios
import tty
import fcntl
import os
import time
from typing import Optional, Dict
from .keyboard import Keyboard, KeyboardState


class SSHKeyboard(Keyboard):
    """\n    Keyboard implementation using terminal input (termios).\n\n    This is used for remote SSH sessions where we need to read raw terminal input.\n    Typically used on Raspberry Pi to accept keyboard input from a remote Mac via SSH.\n    """

    def __init__(self, key_hold_duration: float = 0.15) -> None:
        """
        Initialize SSH keyboard with terminal in cbreak, non‑blocking mode.

        Args:
            key_hold_duration: How long (in seconds) to keep keys "held" after press.
                               This smooths out jittery SSH input by maintaining key
                               state even if network latency causes gaps. Default
                               0.15s (150ms).
        """
        self.stdin_fd = sys.stdin.fileno()
        self.old_settings = None
        self.old_flags = None
        self._setup_terminal()
        self._key_timestamps = {}
        self._key_hold_duration = key_hold_duration
        self._shift_held = False

    def _setup_terminal(self) -> None:
        """Set up terminal in cbreak mode for non‑blocking character input."""
        try:
            # Save original settings and flags so we can restore them in cleanup()
            self.old_settings = termios.tcgetattr(self.stdin_fd)
            self.old_flags = fcntl.fcntl(self.stdin_fd, fcntl.F_GETFL)

            # Put terminal into cbreak mode (no line buffering, minimal processing)
            tty.setcbreak(self.stdin_fd)

            # Make stdin non‑blocking so poll() never blocks the render loop
            fcntl.fcntl(self.stdin_fd, fcntl.F_SETFL,
                        self.old_flags | os.O_NONBLOCK)
        except Exception as e:
            print(f'Warning: Could not setup terminal for keyboard input: {e}')
            self.old_settings = None
            self.old_flags = None

    def _read_terminal_input(self) -> Optional[str]:
        """
        Read all currently available input from stdin in a non‑blocking way.

        Returns:
            A string containing all characters read, or None if no input
            was available.
        """
        chars = ''

        while True:
            try:
                c = sys.stdin.read(1)
            except (BlockingIOError, InterruptedError, OSError):
                # No more data available right now (non‑blocking read)
                break

            if not c:
                # EOF or no data
                break

            chars += c

            # For escape sequences, characters often arrive in a burst; since
            # we're non‑blocking and looping until the OS says "no more data",
            # just keep reading until the exceptions/EOF catch us.

        return chars if chars else None

    def _parse_terminal_input(self, chars: str) -> Optional[str]:
        """
        Parse raw terminal input into standard key names.

        Args:
            chars: Raw characters from terminal.

        Returns:
            Standard key name, or None if not recognized.

        Side effects:
            Updates self._shift_held when a shifted arrow or explicit shift key
            is detected.
        """
        self._shift_held = False
        # Ctrl+C (ETX) should be passed through so higher layers can decide
        # whether to treat it as "quit" or something else.
        if '\x03' in chars:
            return 'ctrl-c'
        if '[1;2A' in chars:
            self._shift_held = True
            return 'up'
        if '[1;2B' in chars:
            self._shift_held = True
            return 'down'
        if '[1;2C' in chars:
            self._shift_held = True
            return 'right'
        if '[1;2D' in chars:
            self._shift_held = True
            return 'left'
        if '[A' in chars:
            return 'up'
        if '[B' in chars:
            return 'down'
        if '[C' in chars:
            return 'right'
        if '[D' in chars:
            return 'left'
        if '[A' in chars:
            return 'up'
        if '[B' in chars:
            return 'down'
        if '[C' in chars:
            return 'right'
        if '[D' in chars:
            return 'left'
        if chars == 'w':
            return 'w'
        if chars == 's':
            return 's'
        if chars == 'a':
            return 'a'
        if chars == 'd':
            return 'd'
        if chars == 'W':
            self._shift_held = True
            return 'w'
        if chars == 'S':
            self._shift_held = True
            return 's'
        if chars == 'A':
            self._shift_held = True
            return 'a'
        if chars == 'D':
            self._shift_held = True
            return 'd'
        if chars == 'z' or chars == 'Z':
            self._shift_held = True
            return 'shift'
        if chars == '\r' or chars == '\n':
            return 'enter'
        if chars == ' ':
            return 'space'
        if chars == '':
            return 'escape'
        if chars == '\x7f':
            return 'backspace'
        if chars == 'b':
            return 'b'
        if chars == 'v':
            return 'v'
        if chars == 'f':
            return 'f'
        if chars == 'g':
            return 'g'
        if chars == 'q':
            return 'q'
        if chars == 'r':
            return 'r'
        if chars == 'e':
            return 'e'
        if chars == 'c':
            return 'c'
        if chars == 't':
            return 't'
        if chars == 'm':
            return 'm'
        if chars == 'n':
            return 'n'
        if chars == 'i':
            return 'i'
        if chars == 'E':
            self._shift_held = True
            return 'e'
        if chars == 'C':
            self._shift_held = True
            return 'c'
        if chars == 'M':
            self._shift_held = True
            return 'm'
        if chars == 'N':
            self._shift_held = True
            return 'n'
        if chars == ',':
            return ','
        if chars == '.':
            return '.'
        if chars == '[':
            return '['
        if chars == ']':
            return ']'
        if chars == ';':
            return ';'
        if chars == '\'':
            return '\''
        if chars == '-':
            return '-'
        if chars == '=':
            return '='
        if chars == '_':
            return '_'
        if chars == '+':
            return '+'
        if chars in '0123456789':
            return chars
        if len(chars) == 1 and chars.isprintable() and (chars != ' '):
            return chars
        return None

    def poll(self) -> KeyboardState:
        """
        Poll terminal for keyboard input.

        Returns:
            KeyboardState with current keyboard state.
        """
        state = KeyboardState()
        current_time = time.time()
        chars = self._read_terminal_input()
        if chars:
            key = self._parse_terminal_input(chars)
            if key:
                state.key_press = key
                self._key_timestamps[key] = current_time
                if self._shift_held:
                    self._key_timestamps['shift'] = current_time
        held_keys = []
        expired_keys = []
        for key, timestamp in self._key_timestamps.items():
            if current_time - timestamp <= self._key_hold_duration:
                held_keys.append(key)
            else:  # inserted
                expired_keys.append(key)
        for key in expired_keys:
            del self._key_timestamps[key]
        state.keys_held = held_keys
        return state

    def cleanup(self):
        """Restore terminal to original settings."""
        if self.old_settings is None:
            return

        try:
            if self.old_flags is not None:
                fcntl.fcntl(self.stdin_fd, fcntl.F_SETFL, self.old_flags)
            termios.tcsetattr(
                self.stdin_fd, termios.TCSADRAIN, self.old_settings)
        except Exception as e:
            print(f'Warning: Could not restore terminal settings: {e}')
