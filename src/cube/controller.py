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

# Import mixer system
from cube.mixer import MixerState, MixerRenderer, MixerSetupMenu, MixerShaderBrowser


class CubeController:
    """Main controller for cube menu system with layered display support."""

    def __init__(self, width: int, height: int, fps: int = 30, num_panels: int = 6,
                 default_brightness: float = 90.0, default_gamma: float = 1.5, **kwargs):
        """
        Initialize cube controller.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            fps: Target frames per second
            num_panels: Number of cube panels/faces (1-6)
            default_brightness: Default brightness percentage (1-90)
            default_gamma: Default gamma correction value (0.5-3.0)
            **kwargs: Additional arguments passed to display backend
        """
        self.window_width = width
        self.window_height = height
        self.target_fps = fps
        self.frame_time = 1.0 / fps
        self.num_panels = num_panels
        self.default_brightness = default_brightness
        self.default_gamma = default_gamma

        # Create display with 3 layers
        # Layer 0: Menu
        # Layer 1: Shader
        # Layer 2: Debug overlay (always on top)
        self.display = Display(width, height, num_layers=3, **kwargs)

        # Use display's actual render resolution (may be scaled down)
        self.width = self.display.width
        self.height = self.display.height

        # Get layer references
        self.menu_layer = self.display.get_layer(0)      # Menu rendering
        self.shader_layer = self.display.get_layer(1)    # Shader output
        self.debug_layer = self.display.get_layer(2)     # Debug overlay (FPS, etc.)

        # Create menu renderer (renders to menu layer)
        self.renderer = MenuRenderer(self.menu_layer)
        self.debug_renderer = MenuRenderer(self.debug_layer)

        # Initialize input handler (decoupled input processing)
        self.input = InputHandler()

        # Initialize settings (shared state)
        self.settings = {
            'debug_ui': False,  # Show FPS and debug info in shaders
            'brightness': default_brightness,  # Default brightness
            'gamma': default_gamma,  # Default gamma
        }

        # Initialize mixer state (needed for mixer menus)
        self.mixer_state = MixerState(num_channels=8)
        self.mixer_renderer = None
        self.in_mixer_mode = False

        # Initialize menu states
        self.states = {
            'main': MainMenu(),
            'visualization_mode': VisualizationModeSelect(),
            'surface_browser': ShaderBrowser(self.width, self.height),
            'volumetric_browser': VolumetricShaderBrowser(self.width, self.height),
            'settings': SettingsMenu(self.settings),
            'mixer_setup': MixerSetupMenu(self.mixer_state, self.width, self.height, num_channels=8),
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
        self.volumetric_display_mode = 'grid'  # 'grid' or 'single'
        self.volumetric_active_face_index = 0  # Active face when in single mode
        # Face names based on num_panels (matches chain order)
        all_face_names = ['front', 'right', 'back', 'left', 'top', 'bottom']
        self.volumetric_face_names = all_face_names[:num_panels]

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
        print("Press 'M' to enter Mixer Mode (A/B crossfader)")
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
                    # Volumetric mode input handling
                    if self.input.is_exit_requested():
                        # Exit volumetric mode, return to menu
                        print("\nReturning to main menu...")
                        self._exit_volumetric_mode()
                        continue

                    # Handle 't' key - toggle display mode / cycle faces
                    if self.input.is_key_pressed('t'):
                        if self.volumetric_display_mode == 'grid':
                            # Switch to single-panel mode, show first face
                            self.volumetric_display_mode = 'single'
                            self.volumetric_active_face_index = 0
                            face_name = self.volumetric_face_names[self.volumetric_active_face_index]
                            print(f"Single panel mode: {face_name.upper()}")
                        else:
                            # In single mode - cycle to next face
                            self.volumetric_active_face_index += 1
                            if self.volumetric_active_face_index >= len(self.volumetric_face_names):
                                # Cycled through all faces - return to grid
                                self.volumetric_display_mode = 'grid'
                                self.volumetric_active_face_index = 0
                                print(f"Grid mode: showing all {len(self.volumetric_face_names)} faces")
                            else:
                                face_name = self.volumetric_face_names[self.volumetric_active_face_index]
                                print(f"Single panel mode: {face_name.upper()}")

                    # Clear menu layer (not used in volumetric mode)
                    self.menu_layer[:, :, :] = 0

                    # Render volumetric scene (all faces)
                    faces = self.volumetric_renderer.render_all_faces()

                    # Layout faces based on display mode
                    if self.volumetric_display_mode == 'grid':
                        # Grid layout - show N-panel chain (how it appears on physical hardware)
                        chain_fb = self._layout_volumetric_chain(faces)

                        # Clear shader layer (black background)
                        self.shader_layer[:, :] = 0

                        # Center the chain in the shader layer without resizing (same as single-panel mode)
                        chain_h, chain_w = chain_fb.shape[:2]
                        layer_h, layer_w = self.shader_layer.shape[:2]

                        # Calculate centered position
                        y_offset = max(0, (layer_h - chain_h) // 2)
                        x_offset = max(0, (layer_w - chain_w) // 2)

                        # Place chain centered (or clipped if larger than layer)
                        y_end = min(y_offset + chain_h, layer_h)
                        x_end = min(x_offset + chain_w, layer_w)
                        chain_y_end = y_end - y_offset
                        chain_x_end = x_end - x_offset

                        self.shader_layer[y_offset:y_end, x_offset:x_end] = chain_fb[:chain_y_end, :chain_x_end]
                    else:
                        # Single-panel mode - show only active face at native face_size
                        face_name = self.volumetric_face_names[self.volumetric_active_face_index]

                        # Clear shader layer (black background)
                        self.shader_layer[:, :] = 0

                        # Check if face exists (should always be true now that we filter face_names)
                        if face_name in faces:
                            face_fb = faces[face_name]

                            # Center the face in the shader layer without resizing
                            face_h, face_w = face_fb.shape[:2]
                            layer_h, layer_w = self.shader_layer.shape[:2]

                            # Calculate centered position
                            y_offset = max(0, (layer_h - face_h) // 2)
                            x_offset = max(0, (layer_w - face_w) // 2)

                            # Place face centered (or clipped if larger than layer)
                            y_end = min(y_offset + face_h, layer_h)
                            x_end = min(x_offset + face_w, layer_w)
                            face_y_end = y_end - y_offset
                            face_x_end = x_end - x_offset

                            self.shader_layer[y_offset:y_end, x_offset:x_end] = face_fb[:face_y_end, :face_x_end]

                    # Clear debug layer
                    self.debug_layer[:, :, :] = 0

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        if self.volumetric_display_mode == 'single':
                            face_name = self.volumetric_face_names[self.volumetric_active_face_index]
                            mode_indicator = f"VOLUMETRIC: {face_name.upper()}"
                        else:
                            mode_indicator = "VOLUMETRIC: GRID"
                        self._render_debug_overlay(mode_indicator=mode_indicator)

                    # Display (layered backend handles compositing and rendering)
                    brightness = self.settings.get('brightness', self.default_brightness)
                    gamma = self.settings.get('gamma', self.default_gamma)
                    self.display.show(brightness=brightness, gamma=gamma)

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
                    brightness = self.settings.get('brightness', self.default_brightness)
                    gamma = self.settings.get('gamma', self.default_gamma)
                    self.display.show(brightness=brightness, gamma=gamma)

                elif self.in_mixer_mode:
                    # Mixer mode input handling
                    if self.input.is_exit_requested():
                        # Exit mixer mode, return to menu
                        print("\nReturning to main menu...")
                        self._exit_mixer_mode()
                        continue

                    # Crossfader control: Q (left) and W (right)
                    pair_changed = False
                    if self.input.is_key_held('q'):
                        pair_changed = self.mixer_state.adjust_crossfader(-0.02)  # Move towards left
                    elif self.input.is_key_held('w'):
                        pair_changed = self.mixer_state.adjust_crossfader(0.02)   # Move towards right

                    # Print active pair when it changes
                    if pair_changed:
                        left_id, right_id = self.mixer_state.get_active_pair_ids()
                        print(f"Crossfading: {left_id} ↔ {right_id} (pair {self.mixer_state.active_pair_index + 1}/{self.mixer_state.num_channels - 1})")

                    # Clear menu layer (not used in mixer mode)
                    self.menu_layer[:, :, :] = 0

                    # Render mixer output to shader layer
                    mixed_fb = self.mixer_renderer.render(self.mixer_state)
                    self.shader_layer[:, :] = mixed_fb

                    # Clear debug layer
                    self.debug_layer[:, :, :] = 0

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        # Show active pair in debug overlay
                        left_id, right_id = self.mixer_state.get_active_pair_ids()
                        mode_indicator = f"MIXER: {left_id}↔{right_id} [{self.mixer_state.crossfader:.2f}]"
                        self._render_debug_overlay(mode_indicator=mode_indicator)

                    # Display (layered backend handles compositing and rendering)
                    brightness = self.settings.get('brightness', self.default_brightness)
                    gamma = self.settings.get('gamma', self.default_gamma)
                    self.display.show(brightness=brightness, gamma=gamma)

                else:
                    # Menu mode input handling
                    key = self.input.get_pressed_key()
                    if key:
                        # Check for mixer mode shortcut
                        if key == 'm':
                            print("[DEBUG] Mixer setup shortcut pressed")
                            running = self._handle_state_transition('mixer_setup')
                            continue

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

                    brightness = self.settings.get('brightness', self.default_brightness)
                    gamma = self.settings.get('gamma', self.default_gamma)
                    self.display.show(brightness=brightness, gamma=gamma)

                # Frame rate limiting (use setting if available)
                target_fps = self.settings.get('fps_limit', self.target_fps)
                target_frame_time = 1.0 / target_fps
                frame_time = time.time() - frame_start
                if frame_time < target_frame_time:
                    time.sleep(target_frame_time - frame_time)

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

        # Check for mixer shader selection command
        if next_state.startswith('mixer_shader_select:'):
            channel_id = next_state.split(':', 1)[1]
            # Create shader browser for this channel
            self.states['mixer_shader_browser'] = MixerShaderBrowser(
                self.mixer_state, channel_id, self.width, self.height
            )
            self.current_state_name = 'mixer_shader_browser'
            self.current_state = self.states['mixer_shader_browser']
            return True

        # Check for mixer shader assignment command
        if next_state.startswith('mixer_assign_shader:'):
            parts = next_state.split(':', 2)
            channel_id = parts[1]
            shader_path = parts[2]
            # Assign shader to channel
            channel = self.mixer_state.get_channel(channel_id)
            channel.load_shader(shader_path, self.width, self.height)
            # Return to mixer setup
            self.current_state_name = 'mixer_setup'
            self.current_state = self.states['mixer_setup']
            return True

        # Check for mixer start command
        if next_state == 'mixer_start':
            self._launch_mixer_mode()
            # Stay in mixer mode (not returning to menu)
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
        print("  T: Toggle between single-face and N-panel chain view")
        # Show actual face cycle based on num_panels
        face_cycle = " → ".join(self.volumetric_face_names) + " → chain"
        print(f"     (Single mode cycles: {face_cycle})")
        print("  ESC: Exit to menu")
        print()

        try:
            # Initialize volumetric renderer if needed
            if self.volumetric_renderer is None:
                # Calculate face size for volumetric panels
                # Panels are square and laid out horizontally in the chain
                # Face size is limited by: width/num_panels and height
                if self.num_panels == 1:
                    # Single panel uses smaller dimension (square)
                    face_size = min(self.width, self.height)
                else:
                    # Multiple panels: each panel is square
                    # Limited by both available width per panel and total height
                    face_size = min(self.width // self.num_panels, self.height)

                self.volumetric_renderer = VolumetricCubeRenderer(
                    face_size=face_size,
                    face_distance=5.0,
                    num_panels=self.num_panels
                )

            # Load shader
            self.volumetric_renderer.load_shader(shader_path)

            # Enter volumetric mode (main loop will handle rendering)
            self.in_volumetric_mode = True

            face_size = self.volumetric_renderer.face_size
            chain_width = face_size * self.num_panels
            print(f"Volumetric shader loaded:")
            print(f"  {self.num_panels} panels at {face_size}×{face_size} each")
            print(f"  Chain layout: {chain_width}×{face_size}")
            print(f"  Starting in {'single-face' if self.volumetric_display_mode == 'single' else 'chain'} mode")
            print("Press 'T' to toggle display mode, ESC to return to menu.")

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

        # Reset display mode to grid
        self.volumetric_display_mode = 'grid'
        self.volumetric_active_face_index = 0

        # Return to main menu
        self.current_state_name = 'main'
        self.current_state = self.states['main']

        print("Returned to menu mode")

    def _launch_mixer_mode(self):
        """Launch mixer mode (shaders should already be loaded via mixer setup)."""
        print(f"\n{'='*60}")
        print(f"MIXER MODE - {self.mixer_state.num_channels} CHANNELS")
        print(f"{'='*60}")
        print("Controls:")
        print("  Q: Crossfade left")
        print("  W: Crossfade right (auto-advances to next pair)")
        print("  ESC: Exit to mixer setup")
        print()

        try:
            # Initialize mixer renderer if needed
            if self.mixer_renderer is None:
                self.mixer_renderer = MixerRenderer(self.width, self.height)

            # Enter mixer mode
            self.in_mixer_mode = True

            # Print all loaded channels
            from pathlib import Path
            print("Loaded channels:")
            for i, channel in enumerate(self.mixer_state.channels):
                channel_id = self.mixer_state.channel_ids[i]
                if channel.has_shader():
                    shader_name = Path(channel.shader_path).name
                    print(f"  {channel_id}: {shader_name}")
                else:
                    print(f"  {channel_id}: [EMPTY]")

            # Print active pair
            print()
            left_id, right_id = self.mixer_state.get_active_pair_ids()
            print(f"Active pair: {left_id} ↔ {right_id} (crossfader: {self.mixer_state.crossfader:.2f})")
            print()
            print("Mixer mode active. Press ESC to return to setup.")

        except Exception as e:
            print(f"\n\nError launching mixer mode: {e}")
            import traceback
            traceback.print_exc()
            self.in_mixer_mode = False
            time.sleep(1.0)

    def _exit_mixer_mode(self):
        """Exit mixer mode and return to mixer setup."""
        # Don't clean up mixer state - we want to keep channel assignments
        # Just exit mixer rendering mode
        self.in_mixer_mode = False

        # Return to mixer setup (not main menu)
        self.current_state_name = 'mixer_setup'
        self.current_state = self.states['mixer_setup']

        print("Returned to mixer setup")

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

        # Add face labels to each panel
        label_renderer = MenuRenderer(combined_fb)
        for face_name, (grid_x, grid_y) in layout.items():
            if face_name not in faces:
                continue

            # Draw label at top-left of each face
            label_x = grid_x * face_size + 2
            label_y = grid_y * face_size + 2
            label_renderer.draw_text(
                face_name.upper(),
                x=label_x,
                y=label_y,
                color=(255, 255, 255),
                scale=1
            )

        return combined_fb

    def _layout_volumetric_chain(self, faces: dict) -> np.ndarray:
        """
        Layout volumetric faces as an N-panel horizontal chain (how they appear on physical hardware).

        Args:
            faces: Dictionary mapping face names to pixel arrays

        Returns:
            Combined framebuffer with N panels laid out horizontally
        """
        # Determine face size from first face
        first_face = next(iter(faces.values()))
        face_size = first_face.shape[0]

        # Map faces to panels in the chain
        # Standard mapping: front, right, back, left, top, bottom
        face_order = ['front', 'right', 'back', 'left', 'top', 'bottom']
        panels_to_show = face_order[:self.num_panels]

        # Create combined framebuffer (horizontal chain)
        combined_height = face_size
        combined_width = face_size * self.num_panels
        combined_fb = np.zeros((combined_height, combined_width, 3), dtype=np.uint8)

        # Place each panel in the chain
        for i, face_name in enumerate(panels_to_show):
            if face_name not in faces:
                continue

            pixels = faces[face_name]
            x_start = i * face_size
            x_end = x_start + face_size

            combined_fb[:, x_start:x_end] = pixels

        # Add face labels to each panel
        label_renderer = MenuRenderer(combined_fb)
        for i, face_name in enumerate(panels_to_show):
            if face_name not in faces:
                continue

            # Draw label at top-left of each panel
            label_x = i * face_size + 2
            label_y = 2
            label_renderer.draw_text(
                face_name.upper(),
                x=label_x,
                y=label_y,
                color=(255, 255, 255),
                scale=1
            )

        return combined_fb

    def _render_debug_overlay(self, mode_indicator: str = None, show_fps: bool = True):
        """
        Render debug UI overlay (FPS, stats, etc.) to debug layer.

        Displays all debug info in a compact, semi-transparent box in the bottom-right corner.

        Args:
            mode_indicator: Optional mode text to display (e.g., "POINTS", "VOXELS")
            show_fps: Whether to show FPS counter (default True)
        """

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
        self.debug_renderer.draw_rect(
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

            self.debug_renderer.draw_text(
                line,
                x=text_x,
                y=text_y + (i * char_height),
                color=color,
                scale=1
            )

    def _render_debug_overlay_on_framebuffer(self, framebuffer: np.ndarray, mode_indicator: str = None, show_fps: bool = True):
        """
        Render debug UI overlay directly onto a framebuffer.

        This is used for modes that bypass the layer system (like volumetric mode).

        Args:
            framebuffer: Target framebuffer to render onto (modified in-place)
            mode_indicator: Optional mode text to display (e.g., "VOLUMETRIC")
            show_fps: Whether to show FPS counter (default True)
        """
        # Get framebuffer dimensions
        fb_height, fb_width = framebuffer.shape[:2]

        # Create a temporary renderer for this framebuffer
        temp_renderer = MenuRenderer(framebuffer)

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
        box_x = fb_width - box_width
        box_y = fb_height - box_height

        # Draw semi-transparent background box
        temp_renderer.draw_rect(
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

            temp_renderer.draw_text(
                line,
                x=text_x,
                y=text_y + (i * char_height),
                color=color,
                scale=1
            )

