#!/usr/bin/env python3
"""
One-shot script to render a shader on the LED matrix.

Usage:
    python shader_to_matrix.py shaders/flame.glsl
    python shader_to_matrix.py shaders/flame.glsl --width 64 --height 64 --fps 30
"""

import os
# Configure PyOpenGL for EGL before any OpenGL imports
os.environ['PYOPENGL_PLATFORM'] = 'egl'

import sys
import time
import argparse
import platform
import numpy as np
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cube.shader import ShaderRenderer


def main():
    parser = argparse.ArgumentParser(
        description="Render GLSL shader on LED matrix via GPU"
    )
    parser.add_argument(
        "shader",
        help="Path to GLSL shader file"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=64,
        help="Display width (default: 64)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=64,
        help="Display height (default: 64)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target frames per second (default: 30)"
    )
    parser.add_argument(
        "--pinout",
        default="AdafruitMatrixBonnet",
        choices=[
            "AdafruitMatrixBonnet",
            "AdafruitMatrixBonnetBGR",
            "AdafruitMatrixHat",
            "AdafruitMatrixHatBGR",
        ],
        help="LED matrix pinout (default: AdafruitMatrixBonnet)"
    )
    parser.add_argument(
        "--num-planes",
        type=int,
        default=10,
        help="Number of bit planes (4-11, default: 10)"
    )
    parser.add_argument(
        "--num-address-lines",
        type=int,
        default=5,
        help="Number of address lines (4 or 5, default: 5)"
    )

    args = parser.parse_args()

    # Validate shader exists
    shader_path = Path(args.shader)
    if not shader_path.exists():
        print(f"Error: Shader file not found: {shader_path}")
        sys.exit(1)

    print(f"Shader: {shader_path}")
    print(f"Resolution: {args.width}x{args.height}")
    print(f"Target FPS: {args.fps}")
    print()

    # Create shader renderer (platform-aware)
    print("Initializing shader renderer...")
    renderer = ShaderRenderer(args.width, args.height)

    # Load shader
    print(f"Loading shader: {shader_path}")
    try:
        renderer.load_shader(str(shader_path))
        print("Shader loaded successfully!")
    except Exception as e:
        print(f"Error loading shader: {e}")
        sys.exit(1)

    # Try to initialize LED matrix (only works on Raspberry Pi)
    matrix = None
    framebuffer = None
    is_preview = platform.system() in ('Darwin', 'Windows')

    if not is_preview:
        try:
            import piomatter

            print("\nInitializing LED matrix...")

            # Map pinout string to enum
            pinout_map = {
                "AdafruitMatrixBonnet": piomatter.Pinout.AdafruitMatrixBonnet,
                "AdafruitMatrixBonnetBGR": piomatter.Pinout.AdafruitMatrixBonnetBGR,
                "AdafruitMatrixHat": piomatter.Pinout.AdafruitMatrixHat,
                "AdafruitMatrixHatBGR": piomatter.Pinout.AdafruitMatrixHatBGR,
            }

            # Create geometry
            geometry = piomatter.Geometry(
                width=args.width,
                height=args.height,
                n_planes=args.num_planes,
                n_addr_lines=args.num_address_lines,
                rotation=piomatter.Orientation.Normal,
                serpentine=False
            )

            # Create framebuffer
            framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)

            # Initialize LED matrix
            matrix = piomatter.PioMatter(
                colorspace=piomatter.Colorspace.RGB888Packed,
                pinout=pinout_map[args.pinout],
                framebuffer=framebuffer,
                geometry=geometry
            )

            print("LED matrix initialized!")

        except ImportError:
            print("Warning: piomatter not available, running in preview mode")
            is_preview = True
        except Exception as e:
            print(f"Warning: Could not initialize LED matrix: {e}")
            print("Running in preview mode")
            is_preview = True

    # Main render loop
    print("\nStarting render loop... (Press Ctrl+C to exit)")
    print("-" * 60)

    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    fps_frames = 0
    target_frame_time = 1.0 / args.fps

    try:
        while True:
            frame_start = time.time()

            # Render shader on GPU
            renderer.render()

            # Read pixels from GPU
            pixels = renderer.read_pixels()

            # Display on LED matrix or preview
            if matrix is not None and framebuffer is not None:
                # Copy to LED matrix framebuffer and display
                framebuffer[:, :, :] = pixels
                matrix.show()
            else:
                # Preview mode - just count frames
                pass

            frame_count += 1
            fps_frames += 1

            # FPS counter every second
            current_time = time.time()
            if current_time - last_fps_time >= 1.0:
                fps = fps_frames / (current_time - last_fps_time)
                mode = "Preview" if is_preview else "LED Matrix"
                print(f"[{mode}] Frame {frame_count:6d} | FPS: {fps:6.2f}", end="\r")
                last_fps_time = current_time
                fps_frames = 0

            # Frame rate limiting
            frame_elapsed = time.time() - frame_start
            if frame_elapsed < target_frame_time:
                time.sleep(target_frame_time - frame_elapsed)

    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("Interrupted by user")

    finally:
        # Display statistics
        total_time = time.time() - start_time
        avg_fps = frame_count / total_time if total_time > 0 else 0

        print(f"\nStatistics:")
        print(f"  Total frames:  {frame_count}")
        print(f"  Total time:    {total_time:.2f}s")
        print(f"  Average FPS:   {avg_fps:.2f}")

        # Clear display
        if matrix is not None and framebuffer is not None:
            print("Clearing display...")
            framebuffer[:, :, :] = 0
            matrix.show()

        print("Done!")


if __name__ == "__main__":
    main()
