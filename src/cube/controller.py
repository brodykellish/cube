"""
Cube Controller - main control loop for LED cube menu system.
"""

import os
import sys

# Configure PyOpenGL platform before any OpenGL imports
# EGL is only for Linux - macOS uses native OpenGL
if sys.platform == 'linux':
    os.environ['PYOPENGL_PLATFORM'] = 'egl'

import time
import numpy as np
from typing import Optional

from cube.display import Display
from cube.input import InputHandler
from cube.menu.menu_renderer import MenuRenderer
from cube.menu.menu_states import (
    MainMenu, ShaderBrowser, SettingsMenu, CameraModeSelect,
    VisualizationModeSelect, VolumetricShaderBrowser
)
from cube.shader import ShaderRenderer, SphericalCamera, StaticCamera

# Import volumetric system
from cube.volumetric import VolumetricCubeRenderer


class CubeController:
    """Main controller for cube menu system with layered display support."""

    def __init__(self, width: int, height: int, fps: int = 30, num_panels: int = 6, **kwargs):
        """
        Initialize cube controller.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            fps: Target frames per second
            num_panels: Number of cube panels/faces (1-6)
            **kwargs: Additional arguments passed to display backend
        """
        self.width = width
        self.height = height
        self.target_fps = fps
        self.frame_time = 1.0 / fps
        self.num_panels = num_panels

        # Create display with 3 layers
        # Layer 0: Menu
        # Layer 1: Shader
        # Layer 2: Debug overlay (always on top)
        self.display = Display(width, height, num_layers=3, **kwargs)

        # Get layer references
        self.menu_layer = self.display.get_layer(0)      # Menu rendering
        self.shader_layer = self.display.get_layer(1)    # Shader output
        self.debug_layer = self.display.get_layer(2)     # Debug overlay (FPS, etc.)

        # Create menu renderer (renders to menu layer)
        self.renderer = MenuRenderer(self.menu_layer)

        # Initialize input handler (decoupled input processing)
        self.input = InputHandler()

        # Initialize settings (shared state)
        self.settings = {
            'debug_ui': False,  # Show FPS and debug info in shaders
        }

        # Initialize menu states
        self.states = {
            'main': MainMenu(),
            'visualization_mode': VisualizationModeSelect(),
            'surface_browser': ShaderBrowser(width, height),
            'volumetric_browser': VolumetricShaderBrowser(width, height),
            'settings': SettingsMenu(self.settings),
        }

        self.current_state_name = 'main'
        self.current_state = self.states['main']

        # Track shader path for camera selection (will be set dynamically)
        self._pending_shader_path = None

        # Shader renderer (initialized when needed)
        self.shader_renderer: Optional[ShaderRenderer] = None
        self.in_shader_mode = False

        # Volumetric renderer (initialized when needed)
        self.volumetric_renderer: Optional[VolumetricCubeRenderer] = None
        self.in_volumetric_mode = False

        # FPS tracking (unified for both menu and shader modes)
        self.frame_count = 0
        self.current_fps = 0.0
        self.fps_frames = 0
        self.last_fps_time = time.time()

        # Store backend kwargs
        self.backend_kwargs = kwargs

        print(f"Controller initialized: {width}×{height} @ {fps} FPS")

    def run(self):
        """Main control loop."""
        print("\nStarting main menu...")
        print("Controls: Arrow keys (or WASD) to navigate, Enter to select, ESC to exit")
        print()

        running = True
        last_frame_time = time.time()

        try:
            while running:
                frame_start = time.time()

                # Handle input - update input handler with events from display
                events = self.display.handle_events()
                self.input.update(events)

                # Check for quit
                if self.input.is_quit_requested():
                    print("[DEBUG] Quit event received")
                    running = False
                    break

                # Process key input based on mode
                if self.in_volumetric_mode:
                    print("[DEBUG] In volumetric mode")
                    # Volumetric mode input handling
                    if self.input.is_exit_requested():
                        # Exit volumetric mode, return to menu
                        print("\nReturning to main menu...")
                        self._exit_volumetric_mode()
                        continue

                    # Clear menu layer (all RGB channels)
                    self.menu_layer[:, :, :] = 0

                    # Render volumetric scene (all faces)
                    faces = self.volumetric_renderer.render_all_faces()

                    # Layout all faces into combined framebuffer
                    combined_fb = self._layout_volumetric_faces(faces)

                    # Clear shader layer and draw combined layout (all RGB channels)
                    self.shader_layer[:, :, :] = 0

                    # Fit the combined framebuffer into the display
                    combined_h, combined_w = combined_fb.shape[:2]
                    display_h = min(combined_h, self.height)
                    display_w = min(combined_w, self.width)
                    self.shader_layer[:display_h, :display_w] = combined_fb[:display_h, :display_w]

                    # Clear debug layer first (all RGB channels)
                    self.debug_layer[:, :, :] = 0

                    # Show FPS if debug_ui enabled (no mode indicator needed)
                    if self.settings.get('debug_ui', False):
                        self._render_debug_overlay()

                    # Display (layered backend handles compositing and rendering)
                    self.display.show()

                elif self.in_shader_mode:
                    # Shader mode input handling
                    if self.input.is_exit_requested():
                        # Exit shader mode, return to menu
                        print("\nReturning to main menu...")
                        self._exit_shader_mode()
                        # Continue to next frame (don't try to render shader after exiting)
                        continue
                    elif self.input.is_key_pressed('reload'):
                        # Reload current shader (R key)
                        if hasattr(self, '_current_shader_path') and self._current_shader_path:
                            try:
                                self.shader_renderer.load_shader(self._current_shader_path)
                                print(f"Shader reloaded: {self._current_shader_path}")
                            except Exception as e:
                                print(f"Error reloading shader: {e}")

                    # Apply input to shader camera controls
                    states = self.input.apply_to_shader_keyboard(self.shader_renderer.keyboard_input)
                    self.shader_renderer.shift_pressed = states['shift']

                    # Clear menu layer (not used in shader mode, all RGB channels)
                    self.menu_layer[:, :, :] = 0

                    # Render shader to its layer
                    self.shader_renderer.render()
                    pixels = self.shader_renderer.read_pixels()
                    self.shader_layer[:, :] = pixels

                    # Clear debug layer (all RGB channels)
                    self.debug_layer[:, :, :] = 0

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        self._render_debug_overlay()

                    # Display (layered backend handles compositing and rendering)
                    self.display.show()

                else:
                    # Menu mode input handling
                    key = self.input.get_pressed_key()
                    if key:
                        print(f"[DEBUG] Processing key in menu: {key}")
                        next_state = self.current_state.handle_input(key)
                        print(f"[DEBUG] Next state: {next_state}")

                        if next_state:
                            print(f"[DEBUG] Transitioning to: {next_state}")
                            running = self._handle_state_transition(next_state)
                            print(f"[DEBUG] Running after transition: {running}")

                    # Clear shader layer (not used in menu mode, all RGB channels)
                    self.shader_layer[:, :, :] = 0

                    # Render current menu state to menu layer
                    self.current_state.render(self.renderer)

                    # Clear debug layer (all RGB channels)
                    self.debug_layer[:, :, :] = 0

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        self._render_debug_overlay()

                    self.display.show()

                # Frame rate limiting
                frame_time = time.time() - frame_start
                if frame_time < self.frame_time:
                    time.sleep(self.frame_time - frame_time)

                # Update FPS (unified for both menu and shader modes)
                self.frame_count += 1
                self.fps_frames += 1
                current_time = time.time()
                if current_time - self.last_fps_time >= 1.0:
                    self.current_fps = self.fps_frames / (current_time - self.last_fps_time)
                    self.last_fps_time = current_time
                    self.fps_frames = 0

                last_frame_time = time.time()

        except Exception as e:
            print(f"\nError in main loop: {e}")
            import traceback
            traceback.print_exc()
            running = False

        finally:
            # Clean up renderers
            if self.shader_renderer is not None:
                try:
                    self.shader_renderer.cleanup()
                except Exception as e:
                    print(f"Warning: Error cleaning up shader renderer: {e}")

            if self.volumetric_renderer is not None:
                try:
                    self.volumetric_renderer.cleanup()
                except Exception as e:
                    print(f"Warning: Error cleaning up volumetric renderer: {e}")

            self.display.cleanup()
            print("\nShutdown complete")

    def _handle_state_transition(self, next_state: str) -> bool:
        """
        Handle transition to next state.

        Args:
            next_state: Name of next state (or special command like 'quit', 'visualize:path:mode', or 'camera_select:path')

        Returns:
            True to continue running, False to quit
        """
        # Check for special commands
        if next_state == 'quit':
            return False

        # Check for camera mode selection command
        if next_state.startswith('camera_select:'):
            shader_path = next_state.split(':', 1)[1]
            # Create camera mode selection state dynamically
            self.states['camera_select'] = CameraModeSelect(shader_path)
            self.current_state_name = 'camera_select'
            self.current_state = self.states['camera_select']
            return True

        # Check for shader visualization command (with optional camera mode)
        if next_state.startswith('visualize:'):
            parts = next_state.split(':')
            shader_path = parts[1]
            camera_mode = parts[2] if len(parts) > 2 else 'spherical'  # Default to spherical

            self._launch_shader_visualization(shader_path, camera_mode)
            # Return to main menu after visualization
            self.current_state_name = 'main'
            self.current_state = self.states['main']
            return True

        # Check for volumetric visualization command
        if next_state.startswith('volumetric:'):
            shader_path = next_state.split(':', 1)[1]
            self._launch_volumetric_visualization(shader_path)
            # Return to main menu after visualization
            self.current_state_name = 'main'
            self.current_state = self.states['main']
            return True

        # Normal state transition
        if next_state in self.states:
            self.current_state_name = next_state
            self.current_state = self.states[next_state]

        return True

    def _launch_shader_visualization(self, shader_path: str, camera_mode: str = 'spherical'):
        """
        Launch shader visualization (in-process rendering in same window).

        Args:
            shader_path: Path to shader file
            camera_mode: Camera mode to use ('static', 'spherical', 'fps')
        """
        print(f"\n{'='*60}")
        print(f"Launching shader: {shader_path}")
        print(f"Camera mode: {camera_mode.upper()}")
        print(f"{'='*60}")

        # Print controls based on camera mode
        if camera_mode == 'static':
            print("Controls:")
            print("  (Camera locked - input passed to shader via iInput)")
            print("  R: Reload shader")
            print("  ESC: Exit to menu")
        elif camera_mode == 'spherical':
            print("Controls:")
            print("  Arrow keys/WASD: Rotate camera")
            print("  Shift+WASD: Rotate with zoom modifier")
            print("  E/C: Zoom in/out")
            print("  R: Reload shader")
            print("  ESC: Exit to menu")
            print()
            print("  Tip: Hold or rapidly press keys for continuous movement")
        else:  # fps or future modes
            print("Controls:")
            print("  (See camera mode documentation)")
            print("  R: Reload shader")
            print("  ESC: Exit to menu")
        print()

        try:
            # Initialize shader renderer if needed
            if self.shader_renderer is None:
                self.shader_renderer = ShaderRenderer(self.width, self.height)

            # Set camera mode
            if camera_mode == 'static':
                self.shader_renderer.set_camera_mode(StaticCamera())
            elif camera_mode == 'spherical':
                self.shader_renderer.set_camera_mode(SphericalCamera())
            elif camera_mode == 'fps':
                print("WARNING: FPS camera mode not yet implemented, using spherical")
                self.shader_renderer.set_camera_mode(SphericalCamera())
            else:
                print(f"WARNING: Unknown camera mode '{camera_mode}', using spherical")
                self.shader_renderer.set_camera_mode(SphericalCamera())

            # Load shader
            self.shader_renderer.load_shader(shader_path)
            self._current_shader_path = shader_path

            # Enter shader mode (main loop will handle rendering)
            self.in_shader_mode = True

            print(f"Shader loaded. Rendering at {self.width}×{self.height}")
            print("Press ESC to return to menu.")

        except Exception as e:
            print(f"\n\nError loading shader: {e}")
            import traceback
            traceback.print_exc()
            self.in_shader_mode = False
            time.sleep(1.0)

    def _exit_shader_mode(self):
        """Exit shader mode and return to menu."""
        # Clean up shader renderer
        if self.shader_renderer is not None:
            try:
                self.shader_renderer.cleanup()
            except Exception as e:
                print(f"Warning: Error cleaning up shader renderer: {e}")
        self.shader_renderer = None
        self.in_shader_mode = False

        # Return to main menu
        self.current_state_name = 'main'
        self.current_state = self.states['main']

        print("Returned to menu mode")

    def _launch_volumetric_visualization(self, shader_path: str):
        """
        Launch volumetric visualization.

        Args:
            shader_path: Path to volumetric shader file
        """
        print(f"\n{'='*60}")
        print(f"Launching volumetric shader: {shader_path}")
        print(f"{'='*60}")
        print("Controls:")
        print("  T: Toggle display mode (cycle through faces)")
        print("  ESC: Exit to menu")
        print()

        try:
            # Initialize volumetric renderer if needed
            if self.volumetric_renderer is None:
                # Infer face size from width, height, and num_panels
                # For example: 128x64 with 2 panels means each panel is 64x64
                if self.num_panels == 1:
                    # Single panel uses smaller dimension
                    face_size = min(self.width, self.height)
                else:
                    # Multiple panels: infer from dimensions
                    # Assume width encompasses multiple panels horizontally
                    face_size = self.width // self.num_panels if self.width >= self.height else min(self.width, self.height)

                self.volumetric_renderer = VolumetricCubeRenderer(
                    face_size=face_size,
                    face_distance=5.0,
                    num_panels=self.num_panels
                )

            # Load shader
            self.volumetric_renderer.load_shader(shader_path)

            # Enter volumetric mode (main loop will handle rendering)
            self.in_volumetric_mode = True

            print(f"Volumetric shader loaded. Rendering {self.num_panels} faces at {self.volumetric_renderer.face_size}×{self.volumetric_renderer.face_size}")
            print("Press ESC to return to menu.")

        except Exception as e:
            print(f"\n\nError loading volumetric shader: {e}")
            import traceback
            traceback.print_exc()
            self.in_volumetric_mode = False
            time.sleep(1.0)

    def _exit_volumetric_mode(self):
        """Exit volumetric mode and return to menu."""
        # Clean up volumetric renderer
        if self.volumetric_renderer is not None:
            try:
                self.volumetric_renderer.cleanup()
            except Exception as e:
                print(f"Warning: Error cleaning up volumetric renderer: {e}")
        self.volumetric_renderer = None
        self.in_volumetric_mode = False

        # Return to main menu
        self.current_state_name = 'main'
        self.current_state = self.states['main']

        print("Returned to menu mode")

    def _layout_volumetric_faces(self, faces: dict) -> np.ndarray:
        """
        Layout all volumetric faces into a single framebuffer for display.

        Args:
            faces: Dictionary mapping face names to pixel arrays

        Returns:
            Combined framebuffer with all faces laid out in a grid pattern
        """
        # Determine face size from first face
        first_face = next(iter(faces.values()))
        face_size = first_face.shape[0]

        # Calculate layout dimensions based on num_panels
        if self.num_panels == 1:
            grid_width, grid_height = 1, 1
        elif self.num_panels == 2:
            grid_width, grid_height = 2, 1
        elif self.num_panels == 3:
            grid_width, grid_height = 3, 1
        elif self.num_panels == 4:
            grid_width, grid_height = 2, 2
        elif self.num_panels == 5:
            grid_width, grid_height = 3, 2
        else:  # 6 panels - use cross pattern
            grid_width, grid_height = 4, 3

        # Create layout positions
        all_faces = ['front', 'back', 'left', 'right', 'top', 'bottom']
        active_faces = all_faces[:self.num_panels]

        if self.num_panels == 6:
            # Cross pattern for 6 faces
            layout = {
                'top': (1, 0),
                'left': (0, 1),
                'front': (1, 1),
                'right': (2, 1),
                'back': (3, 1),
                'bottom': (1, 2),
            }
        else:
            # Simple grid layout for 1-5 faces
            layout = {}
            for i, face_name in enumerate(active_faces):
                if self.num_panels <= 3:
                    # Horizontal layout
                    layout[face_name] = (i, 0)
                elif self.num_panels == 4:
                    # 2x2 grid
                    layout[face_name] = (i % 2, i // 2)
                else:  # 5 panels
                    # 3x2 grid
                    layout[face_name] = (i % 3, i // 3)

        # Create combined framebuffer
        combined_height = grid_height * face_size
        combined_width = grid_width * face_size
        combined_fb = np.zeros((combined_height, combined_width, 3), dtype=np.uint8)

        # Place each face in the layout
        for face_name, (grid_x, grid_y) in layout.items():
            if face_name not in faces:
                continue

            pixels = faces[face_name]
            y_start = grid_y * face_size
            x_start = grid_x * face_size
            y_end = y_start + face_size
            x_end = x_start + face_size

            combined_fb[y_start:y_end, x_start:x_end] = pixels

        return combined_fb

    def _render_debug_overlay(self, mode_indicator: str = None, show_fps: bool = True):
        """
        Render debug UI overlay (FPS, stats, etc.) to debug layer.

        Displays all debug info in a compact, semi-transparent box in the bottom-right corner.

        Args:
            mode_indicator: Optional mode text to display (e.g., "POINTS", "VOXELS")
            show_fps: Whether to show FPS counter (default True)
        """
        debug_renderer = MenuRenderer(self.debug_layer)

        # Collect debug info to display
        debug_lines = []

        # Add FPS if requested
        if show_fps:
            debug_lines.append(f"FPS {self.current_fps:.1f}")

        # Add mode indicator if provided
        if mode_indicator:
            debug_lines.append(f"[{mode_indicator.upper()}]")

        # Don't render anything if there's nothing to show
        if not debug_lines:
            return

        # Calculate box dimensions
        char_width = 6  # Width of one character in scale=1
        char_height = 8  # Height of one line in scale=1
        padding = 2

        # Find longest line to determine box width
        max_line_length = max(len(line) for line in debug_lines)
        box_width = max_line_length * char_width + padding * 2
        box_height = len(debug_lines) * char_height + padding * 2

        # Position in bottom-right corner
        box_x = self.width - box_width
        box_y = self.height - box_height

        # Draw semi-transparent background box
        # Use a dark gray with 50% opacity by drawing at half intensity
        debug_renderer.draw_rect(
            box_x, box_y, box_width, box_height,
            color=(40, 40, 40),  # Dark gray background
            filled=True
        )

        # Render debug text lines
        text_x = box_x + padding
        text_y = box_y + padding

        for i, line in enumerate(debug_lines):
            # Color coding: FPS in green, mode indicators in yellow
            if line.startswith("FPS"):
                color = (0, 255, 0)  # Green
            elif line.startswith("["):
                color = (255, 255, 100)  # Yellow
            else:
                color = (200, 200, 200)  # Light gray

            debug_renderer.draw_text(
                line,
                x=text_x,
                y=text_y + (i * char_height),
                color=color,
                scale=1
            )

