#!/usr/bin/env python3
"""
Color Channel Order Test

Displays a simple RGB test pattern to help identify correct channel order.
Shows 3 vertical bars: Red, Green, Blue (from left to right)
"""

import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import adafruit_blinka_raspberry_pi5_piomatter as piomatter

# Parse arguments
import argparse
parser = argparse.ArgumentParser(description="Test RGB channel order")
parser.add_argument("--width", type=int, default=64)
parser.add_argument("--height", type=int, default=64)
parser.add_argument("--num-address-lines", type=int, default=5, choices=[4, 5])
parser.add_argument("--pinout", type=str, default="AdafruitMatrixBonnet",
                   choices=["AdafruitMatrixBonnet", "AdafruitMatrixBonnetBGR",
                           "AdafruitMatrixHat", "AdafruitMatrixHatBGR"])
parser.add_argument("--channel-order", type=str, default="012",
                   help="Channel order as 3 digits (e.g., '012' for RGB, '210' for BGR)")
args = parser.parse_args()

# Setup
geometry = piomatter.Geometry(
    width=args.width,
    height=args.height,
    n_planes=10,
    n_addr_lines=args.num_address_lines
)

framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)

pinout_map = {
    "AdafruitMatrixBonnet": piomatter.Pinout.AdafruitMatrixBonnet,
    "AdafruitMatrixBonnetBGR": piomatter.Pinout.AdafruitMatrixBonnetBGR,
    "AdafruitMatrixHat": piomatter.Pinout.AdafruitMatrixHat,
    "AdafruitMatrixHatBGR": piomatter.Pinout.AdafruitMatrixHatBGR,
}

matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=pinout_map[args.pinout],
    framebuffer=framebuffer,
    geometry=geometry
)

# Parse channel order
channel_order = [int(c) for c in args.channel_order]

print(f"Color Test Pattern")
print(f"=" * 60)
print(f"Resolution: {args.width}×{args.height}")
print(f"Pinout: {args.pinout}")
print(f"Channel order: {args.channel_order} (0=R, 1=G, 2=B)")
print(f"=" * 60)
print(f"\nDisplaying vertical bars (left to right):")
print(f"  Left:   RED   (255, 0, 0)")
print(f"  Middle: GREEN (0, 255, 0)")
print(f"  Right:  BLUE  (0, 0, 255)")
print(f"\nIf colors are wrong, try:")
print(f"  --channel-order 210  (BGR)")
print(f"  --channel-order 120  (GRB)")
print(f"  Or use --pinout AdafruitMatrixBonnetBGR")
print(f"\nPress Ctrl+C to exit")
print("=" * 60)

try:
    # Create test pattern
    third = args.width // 3

    # Draw three vertical bars
    test_pattern = np.zeros((args.height, args.width, 3), dtype=np.uint8)

    # Red bar (left third)
    test_pattern[:, 0:third, :] = [255, 0, 0]

    # Green bar (middle third)
    test_pattern[:, third:2*third, :] = [0, 255, 0]

    # Blue bar (right third)
    test_pattern[:, 2*third:, :] = [0, 0, 255]

    # Apply channel order
    test_pattern = test_pattern[:, :, channel_order]

    # Display
    framebuffer[:, :, :] = test_pattern
    matrix.show()

    # Keep displaying
    while True:
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n\nClearing display...")
    framebuffer[:, :, :] = 0
    matrix.show()
    print("Done!")
