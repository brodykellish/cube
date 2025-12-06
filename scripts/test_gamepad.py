#!/usr/bin/env python3
"""
Test gamepad/joystick detection and axis mapping.

Plug in your Xbox controller and run this to see axis values.
"""

import pygame
import sys
import time

def main():
    pygame.init()
    pygame.joystick.init()

    print("="*70)
    print("GAMEPAD DETECTION TEST")
    print("="*70)
    print()

    # List all joysticks
    num_joysticks = pygame.joystick.get_count()
    print(f"Joysticks detected: {num_joysticks}")
    print()

    if num_joysticks == 0:
        print("No joysticks/gamepads found!")
        print("Make sure your Xbox controller is plugged in via USB.")
        sys.exit(1)

    # Open first joystick
    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(f"Connected to: {joystick.get_name()}")
    print(f"  Axes: {joystick.get_numaxes()}")
    print(f"  Buttons: {joystick.get_numbuttons()}")
    print(f"  Hats: {joystick.get_numhats()}")
    print()
    print("="*70)
    print("LIVE AXIS VALUES (move sticks to see values)")
    print("="*70)
    print()
    print("Press Ctrl+C to exit")
    print()

    try:
        while True:
            # Process pygame events (required for joystick updates)
            pygame.event.pump()

            # Read all axes
            print("\r", end="")
            axis_values = []
            for i in range(joystick.get_numaxes()):
                value = joystick.get_axis(i)
                axis_values.append(f"Axis{i}: {value:+.2f}")

            print("  ".join(axis_values), end="", flush=True)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nExiting...")

    joystick.quit()
    pygame.quit()

if __name__ == "__main__":
    main()
