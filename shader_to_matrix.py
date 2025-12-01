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
import termios
import tty
import select
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cube.shader import ShaderRenderer


def setup_nonblocking_stdin():
    """Set stdin to non-blocking mode for keyboard input."""
    # Save terminal settings
    old_settings = termios.tcgetattr(sys.stdin)

    # Set terminal to raw mode
    tty.setcbreak(sys.stdin.fileno())

    return old_settings


def restore_stdin(old_settings):
    """Restore terminal to original settings."""
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def read_keyboard_events():
    """Read all available keyboard input (non-blocking)."""
    keys = []

    # Check if input is available
    while select.select([sys.stdin], [], [], 0)[0]:
        char = sys.stdin.read(1)
        if not char:
            break

        # Map characters to key names
        if char == '\x1b':  # Escape sequence
            # Try to read the rest of the escape sequence (with longer timeout)
            if select.select([sys.stdin], [], [], 0.05)[0]:
                char2 = sys.stdin.read(1)
                if char2 == '[':
                    # Wait for third character
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        char3 = sys.stdin.read(1)
                        if char3 == 'A':
                            keys.append('up')
                        elif char3 == 'B':
                            keys.append('down')
                        elif char3 == 'C':
                            keys.append('right')
                        elif char3 == 'D':
                            keys.append('left')
                        # Ignore unrecognized escape sequences
                elif char2 == 'O':
                    # Alternative arrow key format (ESC O A/B/C/D)
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        char3 = sys.stdin.read(1)
                        if char3 == 'A':
                            keys.append('up')
                        elif char3 == 'B':
                            keys.append('down')
                        elif char3 == 'C':
                            keys.append('right')
                        elif char3 == 'D':
                            keys.append('left')
                # Ignore incomplete/unknown escape sequences
            else:
                # Just ESC key (no follow-up within timeout)
                keys.append('escape')
        elif char in ('w', 'W'):
            keys.append('W' if char.isupper() else 'up')
        elif char in ('s', 'S'):
            keys.append('S' if char.isupper() else 'down')
        elif char in ('a', 'A'):
            keys.append('A' if char.isupper() else 'left')
        elif char in ('d', 'D'):
            keys.append('D' if char.isupper() else 'right')
        elif char in ('e', 'E'):
            keys.append('e')
        elif char in ('c', 'C'):
            keys.append('c')
        elif char in ('r', 'R'):
            keys.append('reload')
        elif char in ('q', 'Q', '\x03'):  # q, Q, or Ctrl-C
            keys.append('quit')

    return keys


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
    parser.add_argument(
        "--gamma",
        type=float,
        default=2.2,
        help="Gamma correction value (1.0=linear, 2.2=default, higher=darker blacks, default: 2.2)"
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
    print(f"Gamma: {args.gamma}")
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

    # Set up keyboard input
    print("\nControls:")
    print("  Arrow keys/WASD: Rotate camera")
    print("  Shift+WASD: Rotate with zoom modifier")
    print("  E/C: Zoom in/out")
    print("  R: Reload shader")
    print("  Q or ESC: Quit")
    print()

    old_terminal_settings = setup_nonblocking_stdin()

    # Key state tracking (same as cube_control)
    key_states = {
        'up': 0,
        'down': 0,
        'left': 0,
        'right': 0,
        'e': 0,
        'c': 0,
        'shift': 0,
    }
    key_hold_frames = 12

    # Main render loop
    print("\nStarting render loop... (Press Ctrl+C or Q to exit)")
    print("-" * 60)

    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    fps_frames = 0
    target_frame_time = 1.0 / args.fps

    try:
        while True:
            frame_start = time.time()

            # Read keyboard input
            keys_pressed = read_keyboard_events()

            # Check for quit or reload
            if 'quit' in keys_pressed or 'escape' in keys_pressed:
                print("\nQuitting...")
                break

            if 'reload' in keys_pressed:
                print("\nReloading shader...")
                try:
                    renderer.load_shader(str(shader_path))
                    print("Shader reloaded!")
                except Exception as e:
                    print(f"Error reloading shader: {e}")

            # Update key states
            for key in keys_pressed:
                if key == 'W':
                    key_states['up'] = key_hold_frames
                    key_states['shift'] = key_hold_frames
                elif key == 'S':
                    key_states['down'] = key_hold_frames
                    key_states['shift'] = key_hold_frames
                elif key == 'A':
                    key_states['left'] = key_hold_frames
                    key_states['shift'] = key_hold_frames
                elif key == 'D':
                    key_states['right'] = key_hold_frames
                    key_states['shift'] = key_hold_frames
                elif key in key_states:
                    key_states[key] = key_hold_frames

            # Decay key states
            for k in key_states:
                if key_states[k] > 0:
                    key_states[k] -= 1

            # Apply key states to shader
            keyboard = renderer.keyboard_input
            keyboard.set_key_state('up', key_states['up'] > 0)
            keyboard.set_key_state('down', key_states['down'] > 0)
            keyboard.set_key_state('left', key_states['left'] > 0)
            keyboard.set_key_state('right', key_states['right'] > 0)
            keyboard.set_key_state('forward', key_states['e'] > 0)
            keyboard.set_key_state('backward', key_states['c'] > 0)
            renderer.shift_pressed = key_states['shift'] > 0

            # Render shader on GPU
            renderer.render()

            # Read pixels from GPU
            pixels = renderer.read_pixels()

            # Apply gamma correction if not 1.0
            if args.gamma != 1.0:
                # Normalize to 0-1, apply gamma, scale back to 0-255
                pixels = np.power(pixels / 255.0, args.gamma) * 255.0
                pixels = pixels.astype(np.uint8)

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
        # Restore terminal settings
        restore_stdin(old_terminal_settings)

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
