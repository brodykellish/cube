#!/usr/bin/env python3
"""
Simple test for keyboard input over SSH.
Press keys to test input handling, 'q' to quit, Ctrl-C also works.
"""

import sys
import termios
import tty
import time
import fcntl
import os

def test_keyboard():
    # Setup terminal
    old_settings = termios.tcgetattr(sys.stdin)
    stdin_fd = sys.stdin.fileno()
    old_flags = fcntl.fcntl(stdin_fd, fcntl.F_GETFL)

    try:
        # Use cbreak mode (allows Ctrl-C) and make stdin non-blocking
        tty.setcbreak(stdin_fd)
        fcntl.fcntl(stdin_fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

        print("=" * 60)
        print("KEYBOARD INPUT TEST")
        print("=" * 60)
        print("Press keys to test input:")
        print("  w/s - up/down")
        print("  a/d - left/right")
        print("  arrow keys - navigation")
        print("  Enter/Space - select")
        print("  q or Ctrl-C - quit")
        print("=" * 60 + "\n")

        while True:
            try:
                # Read all available input at once (non-blocking)
                chars = ''
                while True:
                    try:
                        c = sys.stdin.read(1)
                        if c:
                            chars += c
                        else:
                            break
                    except (IOError, OSError):
                        break

                if chars:
                    print(f"Raw input: {repr(chars)}")

                    # Check for Ctrl-C
                    if '\x03' in chars:
                        print("Quitting (Ctrl-C)...")
                        break

                    # Check for escape sequences (arrow keys)
                    if '\x1b[A' in chars:
                        print("Key: UP (arrow)")
                    elif '\x1b[B' in chars:
                        print("Key: DOWN (arrow)")
                    elif '\x1b[C' in chars:
                        print("Key: RIGHT (arrow)")
                    elif '\x1b[D' in chars:
                        print("Key: LEFT (arrow)")
                    # Check for standalone [ (ESC consumed by terminal)
                    elif '[A' in chars:
                        print("Key: UP (arrow, ESC consumed)")
                    elif '[B' in chars:
                        print("Key: DOWN (arrow, ESC consumed)")
                    elif '[C' in chars:
                        print("Key: RIGHT (arrow, ESC consumed)")
                    elif '[D' in chars:
                        print("Key: LEFT (arrow, ESC consumed)")
                    # Single character keys
                    elif chars == 'q':
                        print("Quitting...")
                        break
                    elif chars == 'w':
                        print("Key: UP (w)")
                    elif chars == 's':
                        print("Key: DOWN (s)")
                    elif chars == 'a':
                        print("Key: LEFT (a)")
                    elif chars == 'd':
                        print("Key: RIGHT (d)")
                    elif chars == '\r' or chars == '\n':
                        print("Key: ENTER")
                    elif chars == ' ':
                        print("Key: SPACE")

            except KeyboardInterrupt:
                print("\nQuitting (KeyboardInterrupt)...")
                break

            time.sleep(0.01)

    finally:
        # Restore stdin flags
        fcntl.fcntl(stdin_fd, fcntl.F_SETFL, old_flags)
        # Restore terminal
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("\nTerminal restored.")

if __name__ == "__main__":
    test_keyboard()
