"""
Cube Controller - main control loop for LED cube menu system.
"""

import time
import numpy as np
from typing import Optional

from ..display import Display
from .menu_renderer import MenuRenderer
from .menu_states import (
    MainMenu, ShaderBrowser, SettingsMenu, CameraModeSelect,
    VisualizationModeSelect, VolumetricShaderBrowser
)
from ..shader import ShaderRenderer, SphericalCamera, StaticCamera

# Import volumetric system
import sys
from pathlib import Path
# Add volumetric directory to path
volumetric_path = Path(__file__).parent.parent.parent.parent.parent / "volumetric"
if volumetric_path.exists():
    sys.path.insert(0, str(volumetric_path.parent))
from volumetric import VolumetricCubeRenderer


def _volumetric_preview_window_process(queue, face_size, scale):
    """Run in separate process to display preview window. Must be top-level function for pickling."""
    import pygame
    import numpy as np
    import os

    # Face size is already 50% of original (compressed before sending)
    compressed_face_size = face_size // 2

    # Calculate preview window size (4 faces wide × 3 faces tall)
    preview_width = 4 * compressed_face_size * scale
    preview_height = 3 * compressed_face_size * scale

    # Initialize pygame in this process
    pygame.init()

    # Position window
    os.environ['SDL_VIDEO_WINDOW_POS'] = '700,100'

    screen = pygame.display.set_mode((preview_width, preview_height))
    pygame.display.set_caption("Volumetric Cube - All Faces")

    clock = pygame.time.Clock()

    # Layout positions
    layout = {
        'top': (1, 0),
        'left': (0, 1),
        'front': (1, 1),
        'right': (2, 1),
        'back': (3, 1),
        'bottom': (1, 2),
    }

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

                # Faces are already compressed to 50%, just display them
                actual_face_size = pixels.shape[0]

                # Convert numpy array to pygame surface
                surface = pygame.surfarray.make_surface(np.swapaxes(pixels, 0, 1))

                # Apply scale if needed (usually scale=1)
                if scale > 1:
                    surface = pygame.transform.scale(
                        surface,
                        (actual_face_size * scale, actual_face_size * scale)
                    )

                # Blit to screen
                x = grid_x * actual_face_size * scale
                y = grid_y * actual_face_size * scale
                screen.blit(surface, (x, y))

                # Draw face label
                font = pygame.font.Font(None, 20)
                text = font.render(face_name.upper(), True, (255, 255, 255))
                text_rect = text.get_rect(center=(
                    x + (actual_face_size * scale) // 2,
                    y + 8
                ))
                screen.blit(text, text_rect)

            pygame.display.flip()

        clock.tick(30)  # Limit to 30 FPS

    pygame.quit()


class CubeController:
    """Main controller for cube menu system with layered display support."""

    def __init__(self, width: int, height: int, fps: int = 30, **kwargs):
        """
        Initialize cube controller.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            fps: Target frames per second
            **kwargs: Additional arguments passed to display backend
        """
        self.width = width
        self.height = height
        self.target_fps = fps
        self.frame_time = 1.0 / fps

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
        # Modes: 'front', 'back', 'left', 'right', 'top', 'bottom'
        self.volumetric_display_modes = ['front', 'back', 'left', 'right', 'top', 'bottom']
        self.volumetric_display_mode_index = 0  # Start with front face

        # Volumetric preview window (separate process showing all 6 faces)
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
                    running = False
                    break

                # Process key input based on mode
                if self.in_volumetric_mode:
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

                    # Clear menu layer
                    self.menu_layer[:, :] = 0

                    # Get current display mode
                    current_mode = self.volumetric_display_modes[self.volumetric_display_mode_index]

                    # Render volumetric scene
                    faces = self.volumetric_renderer.render_all_faces()

                    # Update preview window with all faces
                    self._update_volumetric_preview_window(faces)

                    # Display single face in main window
                    face_pixels = faces[current_mode]

                    # Center the face on the display
                    face_size = face_pixels.shape[0]
                    x_offset = (self.width - face_size) // 2
                    y_offset = (self.height - face_size) // 2

                    # Clear shader layer and draw face
                    self.shader_layer[:, :] = 0
                    if x_offset >= 0 and y_offset >= 0:
                        self.shader_layer[y_offset:y_offset+face_size, x_offset:x_offset+face_size] = face_pixels
                    else:
                        # Face is larger than display, crop it
                        crop_x = max(0, -x_offset)
                        crop_y = max(0, -y_offset)
                        display_w = min(face_size - crop_x, self.width)
                        display_h = min(face_size - crop_y, self.height)
                        self.shader_layer[:display_h, :display_w] = face_pixels[crop_y:crop_y+display_h, crop_x:crop_x+display_w]

                    # Clear debug layer first
                    self.debug_layer[:, :] = 0

                    # Always show current face mode indicator
                    self._render_volumetric_mode_indicator(current_mode)

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        self._render_debug_overlay()

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

                    # Handle camera controls for shader
                    import pygame
                    keys = pygame.key.get_pressed()

                    # Update shift key state (modifier for camera controls)
                    self.shader_renderer.shift_pressed = (
                        keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                    )

                    # Update input state
                    self.shader_renderer.handle_input('up', keys[pygame.K_UP] or keys[pygame.K_w])
                    self.shader_renderer.handle_input('down', keys[pygame.K_DOWN] or keys[pygame.K_s])
                    self.shader_renderer.handle_input('left', keys[pygame.K_LEFT] or keys[pygame.K_a])
                    self.shader_renderer.handle_input('right', keys[pygame.K_RIGHT] or keys[pygame.K_d])
                    self.shader_renderer.handle_input('e', keys[pygame.K_e])
                    self.shader_renderer.handle_input('c', keys[pygame.K_c])

                    # Clear menu layer (not used in shader mode)
                    self.menu_layer[:, :] = 0

                    # Render shader to its layer
                    self.shader_renderer.render()
                    pixels = self.shader_renderer.read_pixels()
                    self.shader_layer[:, :] = pixels

                    # Clear debug layer
                    self.debug_layer[:, :] = 0

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        self._render_debug_overlay()

                    # Display (layered backend handles compositing and rendering)
                    self.display.show()

                else:
                    # Menu mode input handling
                    if events['key']:
                        next_state = self.current_state.handle_input(events['key'])

                        if next_state:
                            running = self._handle_state_transition(next_state)

                    # Clear shader layer (not used in menu mode)
                    self.shader_layer[:, :] = 0

                    # Render current menu state to menu layer
                    self.current_state.render(self.renderer)

                    # Clear debug layer
                    self.debug_layer[:, :] = 0

                    # Render debug overlay if enabled (even in menu mode)
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
            print("  Arrow keys/WASD: Rotate camera (or Shift+Up/Down to zoom)")
            print("  E/C: Zoom in/out")
            print("  R: Reload shader")
            print("  ESC: Exit to menu")
        else:  # fps or future modes
            print("Controls:")
            print("  (See camera mode documentation)")
            print("  R: Reload shader")
            print("  ESC: Exit to menu")
        print()

        try:
            # Initialize shader renderer if needed
            if self.shader_renderer is None:
                self.shader_renderer = ShaderRenderer(self.width, self.height, windowed=False)

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
                # Use smaller face size for performance (can be adjusted)
                face_size = min(self.width, self.height)
                self.volumetric_renderer = VolumetricCubeRenderer(
                    face_size=face_size,
                    face_distance=5.0
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

    def _render_debug_overlay(self):
        """Render debug UI overlay (FPS, stats, etc.) to debug layer."""
        # Render FPS counter in top-left corner on debug layer
        fps_text = f"FPS {self.current_fps:.1f}"
        debug_renderer = MenuRenderer(self.debug_layer)
        debug_renderer.draw_text(fps_text, x=2, y=2, color=(0, 255, 0), scale=1)

    def _render_volumetric_mode_indicator(self, mode: str):
        """Render current volumetric display mode indicator."""
        # Show mode in bottom-right corner
        mode_text = f"[{mode.upper()}]"
        debug_renderer = MenuRenderer(self.debug_layer)

        # Calculate position (bottom-right)
        text_width = len(mode_text) * 6  # Approximate character width
        x = self.width - text_width - 2
        y = self.height - 10

        debug_renderer.draw_text(mode_text, x=x, y=y, color=(255, 255, 100), scale=1)

    def _init_volumetric_preview_window(self, face_size: int):
        """Initialize the volumetric preview window showing all 6 faces."""
        from multiprocessing import Process, Queue

        # Store face size for later use
        self.preview_face_size = face_size

        # Create queue for sending face data to preview process
        self.volumetric_preview_queue = Queue(maxsize=2)

        # Start preview window process
        self.volumetric_preview_process = Process(
            target=_volumetric_preview_window_process,
            args=(self.volumetric_preview_queue, face_size, self.volumetric_preview_scale)
        )
        self.volumetric_preview_process.start()

        print(f"Preview window process started (face_size={face_size}, scale={self.volumetric_preview_scale})")

    def _update_volumetric_preview_window(self, faces: dict):
        """
        Update the preview window with all 6 faces in unfolded cube pattern.

        Layout:
               [top]
        [left][front][right][back]
               [bottom]
        """
        if self.volumetric_preview_queue is None or self.volumetric_preview_process is None:
            return

        # Check if process is still alive
        if not self.volumetric_preview_process.is_alive():
            return

        # Compress faces to 50% size before sending to reduce queue data
        from PIL import Image
        compressed_faces = {}
        for face_name, pixels in faces.items():
            # Convert to PIL Image
            img = Image.fromarray(pixels, 'RGB')
            # Resize to 50%
            new_size = (pixels.shape[1] // 2, pixels.shape[0] // 2)
            img_resized = img.resize(new_size, Image.BILINEAR)
            # Convert back to numpy
            compressed_faces[face_name] = np.array(img_resized)

        # Send compressed faces to preview process (non-blocking)
        try:
            # Try to clear old data and put new data
            while not self.volumetric_preview_queue.empty():
                try:
                    self.volumetric_preview_queue.get_nowait()
                except:
                    break
            self.volumetric_preview_queue.put_nowait(compressed_faces)
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
