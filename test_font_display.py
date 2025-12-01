#!/usr/bin/env python3
"""
Test font rendering on LED matrix.
Displays all available characters in rows to verify font rendering.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cube.display import Display
from cube.menu.menu_renderer import MenuRenderer, FONT_5X7

def test_font_display(width=64, height=64, num_address_lines=4):
    """Display all available characters on the matrix."""

    # Create display
    display = Display(width, height, num_layers=1, num_address_lines=num_address_lines)

    # Get framebuffer
    framebuffer = display.get_layer(0)
    renderer = MenuRenderer(framebuffer)

    # Clear to dark background
    renderer.clear((0, 0, 10))

    # Get all available characters
    chars = ''.join(sorted(FONT_5X7.keys()))
    print(f"Available characters: {repr(chars)}")
    print(f"Total characters: {len(chars)}")

    # Font metrics
    char_width = 6  # 5 pixels + 1 spacing
    char_height = 8  # 7 pixels + 1 spacing

    # Calculate how many characters fit per row
    chars_per_row = width // char_width
    print(f"Characters per row: {chars_per_row}")

    # Draw all characters in rows
    x, y = 1, 1
    for i, char in enumerate(chars):
        # Draw character
        renderer.draw_char(char, x, y, color=(255, 255, 255), scale=1)

        # Move cursor
        x += char_width

        # Wrap to next row if needed
        if x + char_width > width:
            x = 1
            y += char_height

            # Stop if we run out of vertical space
            if y + char_height > height:
                break

    # Show on display
    display.show()

    print(f"\nFont test displayed. Press Ctrl-C to exit...")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        display.cleanup()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test font rendering")
    parser.add_argument("--width", type=int, default=64, help="Display width")
    parser.add_argument("--height", type=int, default=64, help="Display height")
    parser.add_argument("--num-address-lines", type=int, default=4, help="Address lines")

    args = parser.parse_args()

    print("=" * 60)
    print("FONT RENDERING TEST")
    print("=" * 60)
    print(f"Resolution: {args.width}×{args.height}")
    print("=" * 60)
    print()

    test_font_display(args.width, args.height, args.num_address_lines)
