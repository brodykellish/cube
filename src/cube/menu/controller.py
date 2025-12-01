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
from .menu_renderer import MenuRenderer
from .menu_states import (
    MainMenu, ShaderBrowser, SettingsMenu, CameraModeSelect,
    VisualizationModeSelect, VolumetricShaderBrowser
)
from cube.shader import ShaderRenderer, SphericalCamera, StaticCamera

# Import volumetric system
import sys
from pathlib import Path
# Add volumetric directory to path
volumetric_path = Path(__file__).parent.parent.parent.parent.parent / "volumetric"
if volumetric_path.exists():
    sys.path.insert(0, str(volumetric_path.parent))
from volumetric import VolumetricCubeRenderer


def _volumetric_preview_window_process(queue, face_size, scale, num_panels):
    """Run in separate process to display preview window. Must be top-level function for pickling."""
    import pygame
    import numpy as np
    import os
    import math

    # Calculate layout dimensions based on num_panels
    # For 1-6 panels, create a reasonable grid layout
    if num_panels == 1:
        grid_width, grid_height = 1, 1
    elif num_panels == 2:
        grid_width, grid_height = 2, 1
    elif num_panels == 3:
        grid_width, grid_height = 3, 1
    elif num_panels == 4:
        grid_width, grid_height = 2, 2
    elif num_panels == 5:
        grid_width, grid_height = 3, 2
    else:  # 6 panels - use cross pattern
        grid_width, grid_height = 4, 3

    # Calculate preview window size (1:1 scale - no downsampling)
    preview_width = grid_width * face_size * scale
    preview_height = grid_height * face_size * scale

    # Initialize pygame in this process
    pygame.init()

    # Position window
    os.environ['SDL_VIDEO_WINDOW_POS'] = '700,100'

    screen = pygame.display.set_mode((preview_width, preview_height))
    pygame.display.set_caption(f"Volumetric Cube - {num_panels} Face{'s' if num_panels > 1 else ''}")

    clock = pygame.time.Clock()

    # Dynamic layout based on num_panels
    all_faces = ['front', 'back', 'left', 'right', 'top', 'bottom']
    active_faces = all_faces[:num_panels]

    # Create layout positions dynamically
    if num_panels == 6:
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
            if num_panels <= 3:
                # Horizontal layout
                layout[face_name] = (i, 0)
            elif num_panels == 4:
                # 2x2 grid
                layout[face_name] = (i % 2, i // 2)
            else:  # 5 panels
                # 3x2 grid
                layout[face_name] = (i % 3, i // 3)

    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    running = False

        # Check for new face data from main process
        faces = None
        while not queue.empty():
            try:
                faces = queue.get_nowait()
            except:
                break

        if faces is not None:
            # Clear screen
            screen.fill((0, 0, 0))

            # Draw each face
            for face_name, (grid_x, grid_y) in layout.items():
                if face_name not in faces:
                    continue

                pixels = faces[face_name]

                # Convert numpy array to pygame surface
                surface = pygame.surfarray.make_surface(np.swapaxes(pixels, 0, 1))

                # Apply scale if needed (usually scale=1 for 1:1 rendering)
                if scale > 1:
                    surface = pygame.transform.scale(
                        surface,
                        (face_size * scale, face_size * scale)
                    )

                # Blit to screen
                x = grid_x * face_size * scale
                y = grid_y * face_size * scale
                screen.blit(surface, (x, y))

                # Draw face label at top-left
                font = pygame.font.Font(None, 20)
                text = font.render(face_name.upper(), True, (255, 255, 255))
                text_rect = text.get_rect(topleft=(x + 2, y + 2))
                screen.blit(text, text_rect)

            pygame.display.flip()

        clock.tick(30)  # Limit to 30 FPS

    pygame.quit()


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

        # Volumetric display mode: cycles through individual faces
        # Modes: dynamically set based on num_panels
        all_face_names = ['front', 'back', 'left', 'right', 'top', 'bottom']
        self.volumetric_display_modes = all_face_names[:num_panels]
        self.volumetric_display_mode_index = 0  # Start with first face

        # Volumetric preview window (separate process showing all active faces)
        self.volumetric_preview_process = None
        self.volumetric_preview_queue = None
        self.volumetric_preview_scale = 1  # Scale factor for preview window (no scaling)

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

                # Handle input
                events = self.display.handle_events()

                if events['quit']:
                    print("[DEBUG] Quit event received")
                    running = False
                    break

                # Process key input based on mode
                if self.in_volumetric_mode:
                    print("[DEBUG] In volumetric mode")
                    # Volumetric mode input handling
                    if events['key']:
                        if events['key'] in ('escape', 'quit', 'back'):
                            # Exit volumetric mode, return to menu
                            print("\nReturning to main menu...")
                            self._exit_volumetric_mode()
                            continue
                        elif events['key'] == 't':
                            # Cycle through display modes
                            self.volumetric_display_mode_index = (self.volumetric_display_mode_index + 1) % len(self.volumetric_display_modes)
                            mode = self.volumetric_display_modes[self.volumetric_display_mode_index]
                            print(f"Display mode: {mode.upper()}")

                    # Clear menu layer (all RGB channels)
                    self.menu_layer[:, :, :] = 0

                    # Get current display mode
                    current_mode = self.volumetric_display_modes[self.volumetric_display_mode_index]

                    # Render volumetric scene
                    faces = self.volumetric_renderer.render_all_faces()

                    # Update preview window with all faces
                    self._update_volumetric_preview_window(faces)

                    # Display single face in main window
                    face_pixels = faces[current_mode]

                    # Draw face at top-left (no centering)
                    face_size = face_pixels.shape[0]

                    # Clear shader layer and draw face (all RGB channels)
                    self.shader_layer[:, :, :] = 0

                    # Crop or pad as needed
                    display_h = min(face_size, self.height)
                    display_w = min(face_size, self.width)
                    self.shader_layer[:display_h, :display_w] = face_pixels[:display_h, :display_w]

                    # Clear debug layer first (all RGB channels)
                    self.debug_layer[:, :, :] = 0

                    # Always show current face mode indicator (and FPS if debug_ui enabled)
                    show_fps = self.settings.get('debug_ui', False)
                    self._render_volumetric_mode_indicator(current_mode, show_fps=show_fps)

                    # Display (layered backend handles compositing and rendering)
                    self.display.show()

                elif self.in_shader_mode:
                    # Shader mode input handling
                    if events['key']:
                        if events['key'] in ('escape', 'quit', 'back'):
                            # Exit shader mode, return to menu
                            print("\nReturning to main menu...")
                            self._exit_shader_mode()
                            # Continue to next frame (don't try to render shader after exiting)
                            continue
                        elif events['key'] == 'reload':
                            # Reload current shader (R key)
                            if hasattr(self, '_current_shader_path') and self._current_shader_path:
                                try:
                                    self.shader_renderer.load_shader(self._current_shader_path)
                                    print(f"Shader reloaded: {self._current_shader_path}")
                                except Exception as e:
                                    print(f"Error reloading shader: {e}")

                    # Handle camera controls for shader using pygame key states
                    keyboard = self.shader_renderer.keyboard_input
                    keys_held = events.get('keys', [])

                    # Map pygame keys to shader keyboard input
                    keyboard.set_key_state('up', 'up' in keys_held or 'w' in keys_held)
                    keyboard.set_key_state('down', 'down' in keys_held or 's' in keys_held)
                    keyboard.set_key_state('left', 'left' in keys_held or 'a' in keys_held)
                    keyboard.set_key_state('right', 'right' in keys_held or 'd' in keys_held)
                    keyboard.set_key_state('forward', 'e' in keys_held)
                    keyboard.set_key_state('backward', 'c' in keys_held)

                    # Update shift state for zoom modifier
                    self.shader_renderer.shift_pressed = 'shift' in keys_held

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
                    if events['key']:
                        print(f"[DEBUG] Processing key in menu: {events['key']}")
                        next_state = self.current_state.handle_input(events['key'])
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
            # Clean up preview window
            self._cleanup_volumetric_preview_window()

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

            # Reset display mode to front face
            self.volumetric_display_mode_index = 0

            # Initialize preview window
            self._init_volumetric_preview_window(self.volumetric_renderer.face_size)

            # Enter volumetric mode (main loop will handle rendering)
            self.in_volumetric_mode = True

            print(f"Volumetric shader loaded. Rendering 6 faces at {self.volumetric_renderer.face_size}×{self.volumetric_renderer.face_size}")
            print("Press ESC to return to menu.")

        except Exception as e:
            print(f"\n\nError loading volumetric shader: {e}")
            import traceback
            traceback.print_exc()
            self.in_volumetric_mode = False
            time.sleep(1.0)

    def _exit_volumetric_mode(self):
        """Exit volumetric mode and return to menu."""
        # Clean up preview window
        self._cleanup_volumetric_preview_window()

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

    def _render_volumetric_mode_indicator(self, mode: str, show_fps: bool = False):
        """
        Render current volumetric display mode indicator.

        Note: This now delegates to _render_debug_overlay to keep all debug UI consolidated.

        Args:
            mode: Display mode name (e.g., "POINTS", "VOXELS")
            show_fps: Whether to also show FPS (controlled by debug_ui setting)
        """
        # Pass mode to debug overlay for consolidated rendering
        self._render_debug_overlay(mode_indicator=mode, show_fps=show_fps)

    def _init_volumetric_preview_window(self, face_size: int):
        """Initialize the volumetric preview window showing all active faces."""
        from multiprocessing import Process, Queue

        # Store face size for later use
        self.preview_face_size = face_size

        # Create queue for sending face data to preview process
        self.volumetric_preview_queue = Queue(maxsize=2)

        # Start preview window process with num_panels
        self.volumetric_preview_process = Process(
            target=_volumetric_preview_window_process,
            args=(self.volumetric_preview_queue, face_size, self.volumetric_preview_scale, self.num_panels)
        )
        self.volumetric_preview_process.start()

        print(f"Preview window process started (face_size={face_size}, scale={self.volumetric_preview_scale}, panels={self.num_panels})")

    def _update_volumetric_preview_window(self, faces: dict):
        """
        Update the preview window with all active faces.

        Layout depends on num_panels:
        - 6 panels: Cross pattern (top, left, front, right, back, bottom)
        - 1-5 panels: Grid layout
        """
        if self.volumetric_preview_queue is None or self.volumetric_preview_process is None:
            return

        # Check if process is still alive
        if not self.volumetric_preview_process.is_alive():
            return

        # Send faces at full resolution (1:1 scale - no downsampling)
        try:
            # Try to clear old data and put new data
            while not self.volumetric_preview_queue.empty():
                try:
                    self.volumetric_preview_queue.get_nowait()
                except:
                    break
            self.volumetric_preview_queue.put_nowait(faces)
        except:
            pass  # Queue full, skip this frame

    def _cleanup_volumetric_preview_window(self):
        """Clean up the volumetric preview window."""
        if self.volumetric_preview_process is not None:
            if self.volumetric_preview_process.is_alive():
                self.volumetric_preview_process.terminate()
                self.volumetric_preview_process.join(timeout=1)
            self.volumetric_preview_process = None
            self.volumetric_preview_queue = None
            print("Preview window closed")
