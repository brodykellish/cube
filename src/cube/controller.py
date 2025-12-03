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
    MainMenu, ShaderBrowser, SettingsMenu,
    VisualizationModeSelect, CubeShaderBrowser,
    DrawPrimitiveBrowser, DrawRenderModeSelect
)
from cube.shader import SphericalCamera, StaticCamera

# Import unified rendering system
from cube.render import PixelMapper, UnifiedRenderer, SurfacePixelMapper, CubePixelMapper

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
        self.face_size = min(self.width, self.height) if self.num_panels == 1 else min(
            self.width // self.num_panels, self.height)

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
            'draw_primitives': DrawPrimitiveBrowser(self.width, self.height),
            'draw_render_select': DrawRenderModeSelect(self.width, self.height),
            'visualization_mode': VisualizationModeSelect(),
            'surface_browser': ShaderBrowser(self.width, self.height),
            'cube_browser': CubeShaderBrowser(self.width, self.height),
            'settings': SettingsMenu(self.settings),
            'mixer_setup': MixerSetupMenu(self.mixer_state, self.width, self.height, num_channels=8),
        }

        self.current_state_name = 'main'
        self.current_state = self.states['main']

        # Track shader path for camera selection (will be set dynamically)
        self._pending_shader_path = None

        # Unified renderer (initialized when needed)
        self.unified_renderer: Optional[UnifiedRenderer] = None

        # Cleanup flag to prevent double-cleanup
        self._cleanup_done = False

        # Navigation stack for menu states
        self._state_stack = []

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
                    running = False
                    break

                # Process key input based on mode
                if self.unified_renderer is not None:
                    # Unified shader rendering input handling
                    if self.input.is_exit_requested():
                        # Exit visualization mode, return to menu
                        print("\nReturning to main menu...")
                        self._exit_visualization_mode()
                        continue
                    elif self.input.is_key_pressed('reload'):
                        # Reload current shader (R key)
                        if hasattr(self, '_current_shader_path') and self._current_shader_path:
                            try:
                                self.unified_renderer.load_shader(
                                    self._current_shader_path)
                                print(
                                    f"Shader reloaded: {self._current_shader_path}")
                            except Exception as e:
                                print(f"Error reloading shader: {e}")

                    # Apply input to shader camera controls
                    states = self.input.apply_to_shader_keyboard(
                        self.unified_renderer.keyboard_input)
                    self.unified_renderer.shift_pressed = states['shift']

                    # Clear menu layer
                    self.menu_layer[:, :, :] = 0

                    # Render using unified renderer (handles both surface and volumetric)
                    framebuffer = self.unified_renderer.render()

                    # Center framebuffer in shader layer
                    self.shader_layer[:, :] = 0
                    fb_h, fb_w = framebuffer.shape[:2]
                    layer_h, layer_w = self.shader_layer.shape[:2]
                    y_offset = max(0, (layer_h - fb_h) // 2)
                    x_offset = max(0, (layer_w - fb_w) // 2)
                    y_end = min(y_offset + fb_h, layer_h)
                    x_end = min(x_offset + fb_w, layer_w)
                    fb_y_end = y_end - y_offset
                    fb_x_end = x_end - x_offset
                    self.shader_layer[y_offset:y_end,
                                      x_offset:x_end] = framebuffer[:fb_y_end, :fb_x_end]

                    # Clear debug layer
                    self.debug_layer[:, :, :] = 0

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        mode_indicator = self._get_visualization_mode_name()
                        self._render_debug_overlay(
                            mode_indicator=mode_indicator)

                    # Display
                    brightness = self.settings.get(
                        'brightness', self.default_brightness)
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
                        # Move towards left
                        pair_changed = self.mixer_state.adjust_crossfader(
                            -0.02)
                    elif self.input.is_key_held('w'):
                        pair_changed = self.mixer_state.adjust_crossfader(
                            0.02)   # Move towards right

                    # Print active pair when it changes
                    if pair_changed:
                        left_id, right_id = self.mixer_state.get_active_pair_ids()
                        print(
                            f"Crossfading: {left_id} ↔ {right_id} (pair {self.mixer_state.active_pair_index + 1}/{self.mixer_state.num_channels - 1})")

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
                        self._render_debug_overlay(
                            mode_indicator=mode_indicator)

                    # Display (layered backend handles compositing and rendering)
                    brightness = self.settings.get(
                        'brightness', self.default_brightness)
                    gamma = self.settings.get('gamma', self.default_gamma)
                    self.display.show(brightness=brightness, gamma=gamma)

                else:
                    # Menu mode input handling
                    key = self.input.get_pressed_key()
                    if key:
                        # Check for back navigation (ESC in menu mode)
                        if key == 'escape' and self._state_stack:
                            self._pop_state()
                            continue

                        # Check for mixer mode shortcut
                        if key == 'm':
                            running = self._handle_state_transition(
                                'mixer_setup')
                            continue

                        next_state = self.current_state.handle_input(key)

                        if next_state:
                            running = self._handle_state_transition(next_state)

                    # Clear shader layer (not used in menu mode, all RGB channels)
                    self.shader_layer[:, :, :] = 0

                    # Render current menu state to menu layer
                    self.current_state.render(self.renderer)

                    # Clear debug layer (all RGB channels)
                    self.debug_layer[:, :, :] = 0

                    # Render debug overlay if enabled
                    if self.settings.get('debug_ui', False):
                        self._render_debug_overlay()

                    brightness = self.settings.get(
                        'brightness', self.default_brightness)
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
                    self.current_fps = self.fps_frames / \
                        (current_time - self.last_fps_time)
                    self.last_fps_time = current_time
                    self.fps_frames = 0

                last_frame_time = time.time()

        except Exception as e:
            print(f"\nError in main loop: {e}")
            import traceback
            traceback.print_exc()
            running = False

        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources (display, renderer, etc.)."""
        # Prevent double cleanup (from both finally and atexit)
        if self._cleanup_done:
            return
        self._cleanup_done = True

        # Clean up renderer
        if self.unified_renderer is not None:
            try:
                self.unified_renderer.cleanup()
            except Exception as e:
                print(f"Warning: Error cleaning up unified renderer: {e}")

        # Clean up display (and terminal if SSH keyboard)
        if self.display:
            self.display.cleanup()

        print("\nShutdown complete")

    def _push_state(self):
        """Push current state onto navigation stack."""
        self._state_stack.append(self.current_state_name)

    def _pop_state(self):
        """Pop state from navigation stack and restore it."""
        if self._state_stack:
            prev_state = self._state_stack.pop()
            self.current_state_name = prev_state
            self.current_state = self.states[prev_state]
        else:
            # If stack is empty, go to main
            self.current_state_name = 'main'
            self.current_state = self.states['main']

    def _handle_state_transition(self, next_state: str) -> bool:
        """
        Handle transition to next state.

        Args:
            next_state: Name of next state (or special command like 'quit', 'visualize:path:mode')

        Returns:
            True to continue running, False to quit
        """
        # Check for special commands
        if next_state == 'quit':
            return False

        print(f"Handling state transition: {next_state}")

        # Check for visualization commands with standardized format
        if next_state.startswith('visualize:'):
            parts = next_state.split(':', 3)
            if len(parts) < 3:
                print(f"Invalid visualization command: {next_state}")
                return True

            mode = parts[1]
            shader_path = parts[2]
            pixel_mapper = None

            # Push current state for return after visualization
            self._push_state()

            pixel_mapper = None
            if mode == 'surface':
                # Surface rendering with spherical camera
                pixel_mapper = SurfacePixelMapper(
                    self.width, self.height, SphericalCamera())
            elif mode == 'cube':
                # Cube rendering with spherical camera
                pixel_mapper = CubePixelMapper(
                    face_size=self.face_size,
                    num_panels=self.num_panels,
                    face_distance=5.0
                )
            else:
                print(f"Unknown visualization mode: {mode}")
                return False

            self._launch_visualization(shader_path, pixel_mapper)
            return True

        if next_state.startswith('draw:'):
            parts = next_state.split(':', 2)
            primitive = parts[1]
            mode = parts[2]
            pixel_mapper = None
            if mode == 'surface':
                pixel_mapper = SurfacePixelMapper(self.width, self.height, SphericalCamera())
            elif mode == 'cube':
                pixel_mapper = CubePixelMapper(
                    face_size=self.face_size,
                    num_panels=self.num_panels,
                    face_distance=5.0
                )
            self._launch_draw_primitive(primitive, pixel_mapper)
            return True

        # Check for DRAW mode transitions
        if next_state.startswith('draw_render_select:'):
            primitive = next_state.split(':', 1)[1]
            self.states['draw_render_select'].set_primitive(primitive)
            # Push current state before transitioning
            if self.current_state_name != 'main':
                self._state_stack.append(self.current_state_name)
            self.current_state_name = 'draw_render_select'
            self.current_state = self.states['draw_render_select']
            return True

        # Check for mixer shader selection command
        if next_state.startswith('mixer_shader_select:'):
            channel_id = next_state.split(':', 1)[1]
            # Create shader browser for this channel
            self.states['mixer_shader_browser'] = MixerShaderBrowser(
                self.mixer_state, channel_id, self.width, self.height
            )
            # Push current state before transitioning
            if self.current_state_name != 'main':
                self._state_stack.append(self.current_state_name)
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
            # Pop back to mixer setup
            self._pop_state()
            return True

        # Check for mixer start command
        if next_state == 'mixer_start':
            self._launch_mixer_mode()
            # Stay in mixer mode (not returning to menu)
            return True

        # Normal state transition
        if next_state in self.states:
            # Push current state onto stack before transitioning
            # Don't push if we're at main menu or going to main
            if self.current_state_name != 'main' and next_state != 'main':
                self._state_stack.append(self.current_state_name)

            self.current_state_name = next_state
            self.current_state = self.states[next_state]

        return True

    def _launch_visualization(self, shader_path: str, pixel_mapper: PixelMapper):
        """
        Visualization launcher for surface rendering mode.

        Args:
            shader_path: Path to shader file
            mode: Should be 'surface' (kept for compatibility)
            camera_mode: Camera mode for surface rendering ('static', 'spherical', 'fps')
        """
        # Print header
        print(f"\n{'='*60}")
        print(f"Launching visualization: {shader_path}")
        print(f"{'='*60}")

        print("Controls:")
        print("  Arrow keys/WASD: Rotate camera")
        print("  Shift+up/down/W/S: Zoom in/out")
        print("  Shift+left/right/A/D: Rotate left/right")
        print("  R: Reload shader")
        print("  ESC: Exit to menu")
        print()
        print("  Tip: Hold or rapidly press keys for continuous movement")
        print()

        try:
            # Create or recreate unified renderer
            if self.unified_renderer is not None:
                self.unified_renderer.cleanup()
            self.unified_renderer = UnifiedRenderer(
                pixel_mapper, self.settings)

            # Load shader
            self.unified_renderer.load_shader(shader_path)
            self._current_shader_path = shader_path

            # Print success message
            print(f"Shader loaded. Rendering at {self.width}×{self.height}")
            print("Press ESC to return to menu.")

        except Exception as e:
            print(f"\n\nError loading visualization: {e}")
            import traceback
            traceback.print_exc()
            self.unified_renderer = None
            time.sleep(1.0)

    def _get_visualization_mode_name(self) -> str:
        """Get the current visualization mode name from the pixel mapper type."""
        if self.unified_renderer is None:
            return "UNKNOWN"

        pixel_mapper = self.unified_renderer.pixel_mapper
        mapper_type = type(pixel_mapper).__name__

        if mapper_type == 'SurfacePixelMapper':
            return "SURFACE"
        elif mapper_type == 'CubePixelMapper':
            return "CUBE"
        else:
            return mapper_type.replace('PixelMapper', '').upper()

    def _exit_visualization_mode(self):
        """Exit visualization mode and return to menu."""
        # Clean up unified renderer
        if self.unified_renderer is not None:
            try:
                self.unified_renderer.cleanup()
            except Exception as e:
                print(f"Warning: Error cleaning up renderer: {e}")
        self.unified_renderer = None

        # Pop from stack to return to previous menu
        self._pop_state()

    def _launch_draw_primitive(self, primitive: str, pixel_mapper: PixelMapper):
        """Launch a geometric primitive with the specified pixel mapper."""
        from cube.shader.template_engine import ShaderTemplateEngine
        import tempfile

        try:
            # Generate shader from template
            engine = ShaderTemplateEngine()
            shader_code = engine.generate(primitive)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.glsl', delete=False) as f:
                f.write(shader_code)
                temp_path = f.name

            self._launch_visualization(temp_path, pixel_mapper)

        except Exception as e:
            print(f"Error launching primitive {primitive}: {e}")
            import traceback
            traceback.print_exc()

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
            print(
                f"Active pair: {left_id} ↔ {right_id} (crossfader: {self.mixer_state.crossfader:.2f})")
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
