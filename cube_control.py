#!/usr/bin/env python3
"""
Cube Control - Master control script for LED cube
Provides menu system for visualization selection and settings
"""

import os
import sys

# Configure PyOpenGL platform before any OpenGL imports
# EGL is only for Linux - macOS uses native OpenGL
if sys.platform == 'linux':
    os.environ['PYOPENGL_PLATFORM'] = 'egl'

import argparse
import time
from pathlib import Path

# Import the menu system
from cube.menu import CubeController


def main():
    parser = argparse.ArgumentParser(
        description="LED Cube Control - Master control interface"
    )

    parser.add_argument(
        "--width", "-w",
        type=int,
        default=64,
        help="Display width in pixels (default: 64)"
    )

    parser.add_argument(
        "--height",
        type=int,
        default=64,
        help="Display height in pixels (default: 64)"
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target frames per second for menu rendering (default: 30)"
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Force preview mode (pygame) even on Raspberry Pi"
    )

    # Hardware-specific options (only used when not in preview mode)
    parser.add_argument(
        "--pinout",
        type=str,
        default="AdafruitMatrixBonnet",
        help="Hardware pinout configuration (default: AdafruitMatrixBonnet)"
    )

    parser.add_argument(
        "--num-planes",
        type=int,
        default=10,
        help="Color depth in bit-planes (4-11, default: 10)"
    )

    parser.add_argument(
        "--num-address-lines",
        type=int,
        default=4,
        help="Address lines: 4 for 32-pixel tall, 5 for 64-pixel (default: 4)"
    )

    parser.add_argument(
        "--num-panels",
        type=int,
        default=6,
        help="Number of cube panels/faces (1-6, default: 6)"
    )

    args = parser.parse_args()

    # Validate num-panels
    if args.num_panels < 1 or args.num_panels > 6:
        parser.error("--num-panels must be between 1 and 6")

    # Print startup banner
    print("=" * 60)
    print("LED CUBE CONTROL")
    print("=" * 60)
    print(f"Resolution: {args.width}×{args.height}")
    print(f"Target FPS: {args.fps}")
    print("=" * 60)
    print()

    # Create and run controller
    try:
        controller = CubeController(
            width=args.width,
            height=args.height,
            fps=args.fps,
            preview=args.preview,
            pinout=args.pinout,
            num_planes=args.num_planes,
            num_address_lines=args.num_address_lines,
            num_panels=args.num_panels
        )

        controller.run()

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
