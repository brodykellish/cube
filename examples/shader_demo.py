#!/usr/bin/env python3
"""
Shader Demo for HUB75 LED Matrix

Displays Shadertoy-format GLSL shaders on HUB75 LED matrix panels using
the Adafruit PioMatter library combined with OpenGL GPU rendering.

This script automatically selects the appropriate renderer:
- On macOS/Windows: Uses pygame preview window (for development)
- On Raspberry Pi/Linux: Uses OpenGL ES for LED matrix output

Usage:
    # Preview mode (macOS/Windows/Linux without matrix)
    python shader_demo.py shaders/cartoon.glsl --width 64 --height 64

    # LED matrix mode (Raspberry Pi with matrix)
    python shader_demo.py shaders/flame.glsl --width 64 --height 64 --pinout AdafruitMatrixBonnet

Examples:
    # Single 64x64 panel with cartoon shader
    python shader_demo.py shaders/cartoon.glsl --width 64 --height 64

    # 128x64 display (two 64x64 panels)
    python shader_demo.py shaders/flame.glsl --width 128 --height 64 --num-address-lines 5

    # Preview mode with larger window
    python shader_demo.py shaders/voronoi.glsl --width 64 --height 64 --preview --scale 10
"""

import sys
import time
import platform
from pathlib import Path
import numpy as np
import piomatter as piomatter


def main():
    # Parse arguments
    parser = piomatter.shader.create_parser(description=__doc__)
    args = parser.parse_args()

    # Determine if we're in preview mode
    is_preview = args.preview or platform.system() in ('Darwin', 'Windows')

    # Print configuration
    piomatter.shader.print_shader_info(
        shader_path=args.shader_path,
        width=args.width,
        height=args.height,
        mode="Preview" if is_preview else "LED Matrix",
        fps=args.fps,
        pinout=args.pinout if not is_preview else None,
        scale=f"{args.scale}x" if is_preview else None
    )

    # Get appropriate renderer
    print("\nInitializing renderer...")
    try:
        renderer = piomatter.shader.get_renderer(
            width=args.width,
            height=args.height,
            preview=args.preview,
            scale=args.scale,
            title=f"Shader: {args.shader_path}"
        )
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Load shader
    print(f"Loading shader: {args.shader_path}")
    renderer.load_shader(str(args.shader_path))
    print("Shader loaded successfully!")

    # set up LED matrix and render loop
    print("\nInitializing LED matrix...")
    # Map orientation string to enum
    orientation_map = {
        "Normal": piomatter.Orientation.Normal,
        "Rotate90": piomatter.Orientation.CCW,
        "Rotate180": piomatter.Orientation.R180,
        "Rotate270": piomatter.Orientation.CW,
    }

    # Map pinout string to enum
    pinout_map = {
        "AdafruitMatrixBonnet": piomatter.Pinout.AdafruitMatrixBonnet,
        "AdafruitMatrixBonnetBGR": piomatter.Pinout.AdafruitMatrixBonnetBGR,
        "AdafruitMatrixHat": piomatter.Pinout.AdafruitMatrixHat,
        "AdafruitMatrixHatBGR": piomatter.Pinout.AdafruitMatrixHatBGR,
        "AdafruitMatrixHatRGB": piomatter.Pinout.AdafruitMatrixHat,  # Alias
    }

    # Create geometry
    geometry = piomatter.Geometry(
        width=args.width,
        height=args.height,
        n_planes=args.num_planes,
        n_addr_lines=args.num_address_lines,
        n_temporal_planes=args.num_temporal_planes,
        rotation=orientation_map[args.orientation],
        serpentine=args.serpentine
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

    # Main render loop for LED matrix
    print("\nRendering to LED matrix... (Press Ctrl+C to exit)")
    print("-" * 60)

    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    fps_frames = 0

    try:
        target_frame_time = 1.0 / args.fps

        while True:
            frame_start = time.time()

            # Render shader to numpy array
            shader_frame = renderer.render()

            # Copy to LED matrix framebuffer
            framebuffer[:, :, :] = shader_frame

            # Display on LED matrix
            matrix.show()

            frame_count += 1
            fps_frames += 1

            # FPS counter
            if args.show_fps:
                current_time = time.time()
                if current_time - last_fps_time >= 1.0:
                    fps = fps_frames / (current_time - last_fps_time)
                    print(f"Frame {frame_count:6d} | FPS: {fps:6.2f}", end="\r")
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
        stats = renderer.get_stats()

        print(f"\nStatistics:")
        print(f"  Total frames:  {stats['frames']}")
        print(f"  Total time:    {stats['elapsed']:.2f}s")
        print(f"  Average FPS:   {stats['avg_fps']:.2f}")

        # Clear display
        print("Clearing display...")
        framebuffer[:, :, :] = 0
        matrix.show()

        print("Done!")


if __name__ == "__main__":
    main()
