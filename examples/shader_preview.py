#!/usr/bin/env python3
"""
Standalone Shader Preview Tool

Displays GLSL shaders in a pygame window for development without LED matrix hardware.
Works on macOS, Linux, and Windows.

This is a standalone version that doesn't require the full Adafruit package to be built.

Usage:
    python shader_preview.py --shader shaders/flame.glsl --width 64 --height 64 --scale 1
    python shader_preview.py -s shaders/flame.glsl --width 64 --height 64
"""

import sys
from pathlib import Path
import piomatter


def main():
    # Parse arguments
    parser = piomatter.shader.create_parser(
        description="Preview GLSL shaders in a window (no LED matrix required)",
        include_matrix_options=False,
        include_preview_options=True
    )
    args = parser.parse_args()

    # Print configuration
    piomatter.shader.print_shader_info(
        shader_path=args.shader_path,
        width=args.width,
        height=args.height,
        mode="Preview (pygame)",
        fps=args.fps,
        scale=f"{args.scale}x"
    )

    # Get preview renderer
    print("\nInitializing preview renderer...")
    try:
        renderer = piomatter.shader.get_renderer(
            width=args.width,
            height=args.height,
            preview=True,  # Force preview mode
            scale=args.scale,
            title=f"Shader Preview: {args.shader_path}",
            audio_file=args.audio  # Pass audio file if provided
        )
    except RuntimeError as e:
        print(f"Error: {e}")
        print("\nMake sure you have installed:")
        print("  pip install pygame PyOpenGL PyOpenGL_accelerate")
        sys.exit(1)

    # Load shader
    print(f"Loading shader: {args.shader_path}")
    try:
        renderer.load_shader(str(args.shader_path))
    except Exception as e:
        print(f"Error loading shader: {e}")
        sys.exit(1)

    # Run interactive preview
    print("\nStarting interactive preview...")
    renderer.run(target_fps=args.fps)


if __name__ == "__main__":
    main()
