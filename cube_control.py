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
import atexit
from pathlib import Path

# Import the controller
from cube.controller import CubeController

def main():
    parser = argparse.ArgumentParser(
        description="LED Cube Control - Master control interface"
    )


    parser.add_argument(
        "--width",
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
        default=5,
        help="Address lines: 4 for 32-pixel tall, 5 for 64-pixel (default: 5)"
    )

    parser.add_argument(
        "--num-panels",
        type=int,
        default=6,
        help="Number of cube panels/faces (1-6, default: 6)"
    )

    parser.add_argument(
        "--brightness",
        type=float,
        default=90.0,
        help="Default brightness percentage (1-90, default: 90)"
    )

    parser.add_argument(
        "--gamma",
        type=float,
        default=2.2,
        help="Default gamma correction value (0.5-3.0, default: 2.2)"
    )

    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help="Content scale factor - scales up internal content within fixed window size. "
             "scale=2 renders at half resolution and scales up for chunky pixels (default: 1)"
    )

    parser.add_argument(
        "--ssh-key-hold",
        type=float,
        default=0.15,
        dest="ssh_key_hold_duration",
        help="SSH keyboard hold duration in seconds for smooth input (0.05-0.5, default: 0.15)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.num_panels < 1 or args.num_panels > 6:
        parser.error("--num-panels must be between 1 and 6")
    if args.brightness < 1 or args.brightness > 90:
        parser.error("--brightness must be between 1 and 90")
    if args.gamma < 0.5 or args.gamma > 3.0:
        parser.error("--gamma must be between 0.5 and 3.0")
    if args.scale < 1 or args.scale > 20:
        parser.error("--scale must be between 1 and 20")
    if args.ssh_key_hold_duration < 0.05 or args.ssh_key_hold_duration > 0.5:
        parser.error("--ssh-key-hold must be between 0.05 and 0.5")

    # Print startup banner
    print("=" * 60)
    print("LED CUBE CONTROL")
    print("=" * 60)
    print(f"Window Size: {args.width}×{args.height}")
    if args.scale > 1:
        render_width = args.width // args.scale
        render_height = args.height // args.scale
        print(f"Render Resolution: {render_width}×{render_height} (scale {args.scale}x)")
    print(f"Target FPS: {args.fps}")
    print(f"Default Brightness: {args.brightness}%")
    print(f"Default Gamma: {args.gamma}")
    print("=" * 60)
    print()

    # Create and run controller
    controller = None
    try:
        controller = CubeController(
            width=args.width,
            height=args.height,
            num_panels=args.num_panels,
            num_address_lines=args.num_address_lines,
            fps=args.fps,
            default_brightness=args.brightness,
            default_gamma=args.gamma,
            scale=args.scale,
            ssh_key_hold_duration=args.ssh_key_hold_duration
        )

        # Register cleanup as atexit handler (safety net)
        atexit.register(controller.cleanup)

        controller.run()

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always cleanup, even on error
        if controller:
            controller.cleanup()


if __name__ == "__main__":
    main()
