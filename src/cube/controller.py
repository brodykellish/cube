"""
Refactored LED Cube Controller with clean menu navigation and visualization management.

This demonstrates a cleaner architecture that:
- Separates menu navigation from visualization configuration
- Uses structured actions instead of string parsing
- Eliminates special cases and legacy redirects
"""

import time
from pathlib import Path
from typing import Optional
import tempfile

from cube.display import Display
from cube.input import InputHandler
from cube.menu.menu_renderer import MenuRenderer
from cube.menu.navigation import MenuNavigator
from cube.menu.actions import (
    MenuAction, QuitAction, LaunchVisualizationAction, MixerAction, PromptAction,
    ShaderSelectionAction
)
from cube.menu.menu_states import (
    MainMenu, VisualizationModeSelect, ShaderBrowser, SettingsMenu
)
from cube.menu.prompt_menu import PromptMenuState
from cube.render import UnifiedRenderer, SurfacePixelMapper, CubePixelMapper
from cube.shader import SphericalCamera
from cube.midi import MIDIState, MIDIKeyboardDriver, MIDIUniformSource, USBMIDIDriver, load_midi_config


class CubeController:
    """
    Main controller with clean separation of concerns.

    The controller handles:
    - Menu navigation (delegated to MenuNavigator)
    - Visualization launching based on structured actions
    - Main run loop
    """

    def __init__(self, width: int, height: int, num_panels: int = 6, fps: int = 60,
                 default_brightness: float = 60.0, default_gamma: float = 2.2,
                 scale: int = 1, **kwargs):
        """Initialize the controller."""

        self.window_width = width
        self.window_height = height
        self.fps = fps
        self.frame_time = 1.0 / fps
        self.num_panels = num_panels
        self.default_brightness = default_brightness
        self.default_gamma = default_gamma

        # Create display with 3 layers
        # Layer 0: Menu
        # Layer 1: Shader
        # Layer 2: Debug overlay (always on top)
        self.display = Display(
            width, height, num_layers=3, scale=scale, **kwargs)

        # Use display's actual render resolution (may be scaled down)
        self.width = self.display.width
        self.height = self.display.height

        # Calculate panel dimensions (can be rectangular for non-square displays)
        if self.num_panels == 1:
            self.panel_width = self.width
            self.panel_height = self.height
        else:
            # Horizontal layout: divide width, use full height
            self.panel_width = self.width // self.num_panels
            self.panel_height = self.height

        # Get layer references
        self.menu_layer = self.display.get_layer(0)      # Menu rendering
        self.shader_layer = self.display.get_layer(1)    # Shader output
        self.debug_layer = self.display.get_layer(
            2)     # Debug overlay (FPS, etc.)

        # Settings
        self.settings = {
            'debug_ui': False,
            'debug_axes': False,
            'brightness': default_brightness,
            'gamma': default_gamma,
            'fps_limit': fps,
        }

        self.input_handler = InputHandler()

        # Create menu renderer (renders directly to menu layer)
        self.menu_renderer = MenuRenderer(self.menu_layer)

        # Initialize menu navigation (use display's actual dimensions)
        self.menu_navigator = MenuNavigator(
            self.width, self.height, self.settings)
        self._register_menus()

        # MIDI parameter control
        self.midi_state = MIDIState(num_channels=4)
        self.midi_keyboard = MIDIKeyboardDriver(self.midi_state)
        self.midi_uniform_source = MIDIUniformSource(self.midi_state)

        # USB MIDI controller (optional, requires config)
        self.midi_config = load_midi_config()
        self.usb_midi = None
        if self.midi_config:
            self.usb_midi = USBMIDIDriver(self.midi_state, self.midi_config)
            if self.usb_midi.is_connected():
                print(
                    f"USB MIDI controller connected: {self.usb_midi.connected_device}")
        else:
            print("No MIDI config found (midi_config.yml) - USB MIDI disabled")

        # Gamepad input (optional, auto-detected)
        self.gamepad = None
        try:
            # Only initialize on pygame-based platforms
            if hasattr(self.display.backend, 'pygame'):
                from cube.input.gamepad import GamepadCameraInput
                self.gamepad = GamepadCameraInput(self.display.backend.pygame, joystick_index=0)
                if not self.gamepad.is_connected():
                    self.gamepad = None
        except Exception as e:
            # Silently ignore if no gamepad (not an error condition)
            pass

        # Visualization state
        self.unified_renderer: Optional[UnifiedRenderer] = None
        self.current_shader_path: Optional[Path] = None
        self.is_visualizing = False

        # Track if we launched from prompt (for return navigation)
        self.launched_from_prompt = False

        # FPS tracking
        self.fps_counter = 0
        self.fps_last_time = time.time()
        self.fps_current = 0.0

        # Cleanup flag to prevent double-cleanup
        self._cleanup_done = False

    def _register_menus(self):
        """Register all menu states with the navigator."""
        self.menu_navigator.register_menu('main', MainMenu())
        self.menu_navigator.register_menu(
            'visualize', VisualizationModeSelect())
        self.menu_navigator.register_menu(
            'surface_browser', ShaderBrowser('surface'))
        self.menu_navigator.register_menu(
            'cube_browser', ShaderBrowser('cube'))
        self.menu_navigator.register_menu('settings', SettingsMenu())

        shaders_dir = Path(__file__).parent.parent.parent / 'shaders'
        # Pass shaders_dir directly - PromptMenuState will create the 'generated' subdirectory
        self.menu_navigator.register_menu(
            'prompt', PromptMenuState(self.width, self.height, shaders_dir))

        # Start at main menu
        self.menu_navigator.navigate_to('main')

    def run(self):
        """Main run loop."""
        print("\nStarting cube controller...")
        print("Controls: Arrow keys to navigate, Enter to select, ESC to back/exit")

        clock = time.time()
        running = True
        last_frame_time = time.time()

        while running:
            frame_start = time.time()
            dt = frame_start - last_frame_time
            last_frame_time = frame_start

            # Handle input - get events from display and update input handler
            events = self.display.handle_events()
            self.input_handler.update(events)

            # Check for quit
            if self.input_handler.is_quit_requested():
                running = False
                break

            # Get the key that was pressed this frame
            key = self.input_handler.get_pressed_key()

            if self.is_visualizing:
                # Handle visualization input
                if self.input_handler.is_exit_requested():
                    self._stop_visualization()
                elif self.input_handler.is_key_pressed('r', 'reload') and self.current_shader_path:
                    self._reload_shader()
                elif self.input_handler.is_key_pressed('i'):
                    # Toggle debug UI
                    self.settings['debug_ui'] = not self.settings.get('debug_ui', False)
                    status = "enabled" if self.settings['debug_ui'] else "disabled"
                    print(f"Debug UI {status}")
                else:
                    # Route key presses to uniform sources
                    if key:
                        self._route_visualization_key(key)

                    # Update camera and MIDI from held keys (for smooth movement)
                    self._update_camera_from_held_keys()
                    self._update_midi_from_held_keys(dt)
            else:
                # Handle menu input
                if key:
                    action = self.menu_navigator.handle_input(key)
                    if action:
                        running = self._handle_action(action)

                # Handle paste events
                paste_text = self.input_handler.get_paste_text()
                if paste_text:
                    # Pass paste to current menu state if it supports it
                    if hasattr(self.menu_navigator.current_state, 'handle_paste'):
                        self.menu_navigator.current_state.handle_paste(
                            paste_text)

                # Update menu state (for animations, async operations, etc.)
                action = self.menu_navigator.update(dt)
                if action:
                    running = self._handle_action(action)

            # Render
            if self.is_visualizing:
                self._render_visualization()
            else:
                self._render_menu()

            # Update FPS counter
            self.fps_counter += 1
            current_time = time.time()
            if current_time - self.fps_last_time >= 1.0:
                self.fps_current = self.fps_counter / (current_time - self.fps_last_time)
                self.fps_counter = 0
                self.fps_last_time = current_time

            # Frame rate limiting (use current setting, not initial value)
            frame_time = time.time() - frame_start
            target_fps = self.settings.get('fps_limit', self.fps)
            sleep_time = (1.0 / target_fps) - frame_time
            if sleep_time > 0:
                time.sleep(sleep_time)

        print("Shutdown complete")
        self.cleanup()

    def cleanup(self):
        """Clean up resources (display, input, etc.)."""
        # Clean up USB MIDI
        if self.usb_midi:
            self.usb_midi.cleanup()

        # Clean up gamepad
        if hasattr(self, 'gamepad') and self.gamepad:
            self.gamepad.cleanup()

        # Prevent double cleanup (from both finally and atexit)
        if self._cleanup_done:
            return
        self._cleanup_done = True

        if self.display:
            self.display.cleanup()
        if self.unified_renderer:
            self.unified_renderer.cleanup()

    def _handle_action(self, action: MenuAction) -> bool:
        """
        Handle an action from the menu system.

        Returns:
            True to continue running, False to quit.
        """
        if isinstance(action, QuitAction):
            return False

        elif isinstance(action, PromptAction):
            # Navigate to prompt menu
            self.menu_navigator.navigate_to('prompt')
            return True

        elif isinstance(action, LaunchVisualizationAction):
            self._launch_visualization(action)
            return True

        elif isinstance(action, ShaderSelectionAction):
            # Convert shader selection to visualization launch
            # This happens when user selects a shader from browser
            if action.pixel_mapper:
                launch_action = LaunchVisualizationAction(
                    shader_path=action.shader_path,
                    pixel_mapper=action.pixel_mapper
                )
                self._launch_visualization(launch_action)
            else:
                print(
                    f"Warning: Shader selected but no pixel mapper specified: {action.shader_path}")
            return True

        elif isinstance(action, MixerAction):
            # TODO: Handle mixer actions
            print(f"Mixer action not yet implemented: {action}")
            return True

        return True

    def _launch_visualization(self, action: LaunchVisualizationAction):
        """Launch a visualization based on the action configuration."""
        # Track if launching from prompt (for return navigation)
        self.launched_from_prompt = (
            self.menu_navigator.current_state.name == 'prompt')

        print(f"\n{'='*60}")
        print(f"Launching visualization")
        print(f"Pixel mapper: {action.pixel_mapper}")

        # Generate or load shader
        shader_path = action.shader_path

        print(f"Shader: {shader_path}")
        print(f"{'='*60}")
        print("Controls:")
        print("  WASD: Rotate view")
        print("  Shift+WS: Zoom in/out")
        print("  Shift+AD: Roll left/right")
        if self.gamepad and self.gamepad.is_connected():
            print("\nGamepad:")
            print("  Left Stick: Rotate camera")
            print("  Right Stick Y: Zoom in/out")
        print("\n  R: Reload shader")
        print("  I: Toggle debug info (FPS, camera)")
        print("  ESC: Return to menu")
        print("\nMIDI Parameters:")
        print("  n/m: CC0 (param0) -/+")
        print("  ,/. : CC1 (param1) -/+")
        print("  [/] : CC2 (param2) -/+")
        print("  ;/' : CC3 (param3) -/+")

        try:
            # Create pixel mapper
            if action.pixel_mapper == 'surface':
                camera = SphericalCamera()
                pixel_mapper = SurfacePixelMapper(
                    self.width, self.height, camera)
            elif action.pixel_mapper == 'cube':
                print(
                    f"Cube panel dimensions: {self.panel_width}×{self.panel_height}")
                print(f"Cube num panels: {self.num_panels}")
                pixel_mapper = CubePixelMapper(
                    face_width=self.panel_width,
                    face_height=self.panel_height,
                    num_panels=self.num_panels
                )
            else:
                raise ValueError(
                    f"Unknown pixel mapper: {action.pixel_mapper}")

            # Create renderer with all uniform sources registered
            if self.unified_renderer:
                self.unified_renderer.cleanup()

            # Register all uniform sources in one place
            # Note: CameraUniformSource is automatically created by UnifiedRenderer
            uniform_sources = [
                self.midi_uniform_source,  # MIDI parameter control
                # Add other sources here (audio, OSC, etc.)
            ]

            self.unified_renderer = UnifiedRenderer(
                pixel_mapper,
                self.settings,
                uniform_sources=uniform_sources
            )

            # Load shader
            self.unified_renderer.load_shader(str(shader_path))

            self.current_shader_path = shader_path
            self.is_visualizing = True

            print("Visualization started. Press ESC to return to menu.")

        except Exception as e:
            print(f"Error launching visualization: {e}")
            import traceback
            traceback.print_exc()
            self.is_visualizing = False

    def _stop_visualization(self):
        """Stop current visualization and return to menu."""
        if self.launched_from_prompt:
            print("Returning to prompt...")
            # Return to prompt menu for refinement
            self.menu_navigator.navigate_to('prompt')
        else:
            print("Returning to menu...")

        if self.unified_renderer:
            self.unified_renderer.cleanup()
            self.unified_renderer = None
        self.is_visualizing = False
        self.current_shader_path = None
        self.launched_from_prompt = False

    def _route_visualization_key(self, key: str):
        """
        Route keyboard input to appropriate uniform source.

        Handles discrete key presses (MIDI controls).

        Args:
            key: Key that was pressed
        """
        # MIDI control keys (discrete presses)
        if self.midi_keyboard.handle_key(key):
            # Key was a MIDI control - print feedback
            cc_num = self.midi_keyboard.get_cc_for_key(key)
            if cc_num is not None:
                value = self.midi_state.get_cc(cc_num)
                name = self.midi_state.get_cc_name(cc_num)
                print(f"MIDI: {name} = {value} ({value/127.0:.2f})")

    def _update_midi_from_held_keys(self, dt: float):
        """
        Update MIDI CC values from currently held keys.

        This provides smooth continuous MIDI parameter adjustment.
        Called every frame during visualization.
        """
        held_keys = self.input_handler.get_held_keys()
        self.midi_keyboard.update_from_held_keys(held_keys, dt)

    def _update_camera_from_held_keys(self):
        """
        Update camera uniform source from held keys and gamepad.

        Combines keyboard and gamepad input for camera control.
        Called every frame during visualization.
        """
        if not self.unified_renderer:
            return

        camera_source = self.unified_renderer.camera_source

        # Get keyboard input
        kb_up = self.input_handler.is_key_held('w', 'up')
        kb_down = self.input_handler.is_key_held('s', 'down')
        kb_left = self.input_handler.is_key_held('a', 'left')
        kb_right = self.input_handler.is_key_held('d', 'right')
        kb_shift = self.input_handler.is_key_held('shift')

        # Get gamepad input if available
        gp_state = {'up': 0.0, 'down': 0.0, 'left': 0.0, 'right': 0.0, 'forward': 0.0, 'backward': 0.0}
        gp_shift = False

        if self.gamepad:
            gp_state = self.gamepad.poll()
            gp_shift = self.gamepad.is_shift_pressed()

        # Combine keyboard and gamepad input (additive)
        # Keyboard: boolean (0 or 1), Gamepad: float (0-1)
        camera_source.set_key_state('up', kb_up or gp_state['up'] > 0.1)
        camera_source.set_key_state('down', kb_down or gp_state['down'] > 0.1)
        camera_source.set_key_state('left', kb_left or gp_state['left'] > 0.1)
        camera_source.set_key_state('right', kb_right or gp_state['right'] > 0.1)
        camera_source.set_key_state('forward', gp_state['forward'] > 0.1)
        camera_source.set_key_state('backward', gp_state['backward'] > 0.1)
        camera_source.shift_pressed = kb_shift or gp_shift

    def _reload_shader(self):
        """Reload current shader."""
        if self.unified_renderer and self.current_shader_path:
            print(f"Reloading shader: {self.current_shader_path}")
            try:
                self.unified_renderer.load_shader(
                    str(self.current_shader_path))
            except Exception as e:
                print(f"Error reloading shader: {e}")

    def _render_debug_overlay(self):
        """Render debug information (FPS, camera position, etc.) to debug layer."""
        # Clear debug layer first
        self.debug_layer[:, :, :] = 0

        if not self.settings.get('debug_ui', False):
            return  # Debug UI disabled

        # Create a temporary renderer for the debug layer
        from cube.menu.menu_renderer import MenuRenderer
        debug_renderer = MenuRenderer(self.debug_layer)

        # Get display dimensions
        height, width = self.debug_layer.shape[:2]

        # Character dimensions (scale=1): 4 pixels wide, 8 pixels tall
        char_width = 4
        char_height = 8
        line_spacing = 2

        # Build debug text lines
        lines = []
        fps_text = f"FPS: {self.fps_current:.1f}"
        lines.append(fps_text)

        # If visualizing, show camera info
        if self.is_visualizing and self.unified_renderer:
            try:
                # Get camera position from camera uniform source
                camera_uniforms = self.unified_renderer.camera_source.get_uniforms()
                cam_pos = camera_uniforms.get('iCameraPos', (0, 0, 0))

                # Format camera position (limit to 1 decimal place for readability)
                cam_text = f"Cam: ({cam_pos[0]:.1f},{cam_pos[1]:.1f},{cam_pos[2]:.1f})"
                lines.append(cam_text)

            except Exception as e:
                # Silently ignore camera info errors
                pass

        # Show MIDI parameters
        try:
            # Get normalized parameter values (0-1)
            p0 = self.midi_state.get_normalized(0)
            p1 = self.midi_state.get_normalized(1)
            p2 = self.midi_state.get_normalized(2)
            p3 = self.midi_state.get_normalized(3)

            # Format parameters (2 decimal places)
            params_text = f"P: {p0:.2f} {p1:.2f} {p2:.2f} {p3:.2f}"
            lines.append(params_text)

        except Exception as e:
            # Silently ignore parameter errors
            pass

        # Calculate max text width
        max_text_len = max(len(line) for line in lines) if lines else 0
        text_width = max_text_len * char_width

        # Position in bottom-right corner with 2-pixel padding
        x_pos = width - text_width - 2
        y_start = height - (len(lines) * (char_height + line_spacing)) - 2

        # Render each line from bottom to top
        for i, line in enumerate(lines):
            y_pos = y_start + i * (char_height + line_spacing)
            # Color: FPS in green, camera in cyan, params in yellow
            if i == 0:
                color = (0, 255, 0)  # FPS - green
            elif line.startswith('Cam:'):
                color = (100, 200, 255)  # Camera - cyan
            elif line.startswith('P:'):
                color = (255, 255, 100)  # Parameters - yellow
            else:
                color = (200, 200, 200)  # Default - white
            debug_renderer.draw_text(line, x_pos, y_pos, color=color, scale=1)

    def _render_menu(self):
        """Render current menu."""
        # Clear shader layer when in menu mode
        self.shader_layer[:, :, :] = 0

        # Clear menu layer first to ensure clean render
        self.menu_layer[:, :, :] = 0

        # Render menu to menu layer
        self.menu_navigator.render(self.menu_renderer)

        # Render debug overlay (FPS, etc.)
        self._render_debug_overlay()

        # Show the composed layers
        self.display.show(
            brightness=self.settings.get('brightness', 90.0),
            gamma=self.settings.get('gamma', 1.0)
        )

    def _render_visualization(self):
        """Render current visualization."""
        if self.unified_renderer:
            # Update pixel mapper cameras from main camera (for cube mode)
            if hasattr(self.unified_renderer.pixel_mapper, 'update_from_camera'):
                camera_uniforms = self.unified_renderer.camera_source.get_uniforms()
                self.unified_renderer.pixel_mapper.update_from_camera(
                    camera_uniforms)

            # Clear menu layer during visualization
            self.menu_layer[:, :, :] = 0

            # Render shader output to shader layer
            # All uniform sources (camera, MIDI, etc.) updated in render()
            framebuffer = self.unified_renderer.render()

            # Copy framebuffer to shader layer, handling size mismatch
            fb_height, fb_width = framebuffer.shape[:2]
            layer_height, layer_width = self.shader_layer.shape[:2]

            if fb_height == layer_height and fb_width == layer_width:
                # Direct copy if sizes match
                self.shader_layer[:] = framebuffer
            else:
                # Clear shader layer first
                self.shader_layer[:, :, :] = 0

                # Center the framebuffer in the shader layer
                y_offset = (layer_height - fb_height) // 2
                x_offset = (layer_width - fb_width) // 2

                # Copy framebuffer to centered position
                self.shader_layer[y_offset:y_offset+fb_height,
                                  x_offset:x_offset+fb_width] = framebuffer

            # Render debug overlay (FPS, camera info, etc.)
            self._render_debug_overlay()

            # Show the composed layers with brightness and gamma
            self.display.show(
                brightness=self.settings.get('brightness', 90.0),
                gamma=self.settings.get('gamma', 1.0)
            )


# Example usage
if __name__ == "__main__":
    controller = CubeController(
        width=256,
        height=128,
        num_panels=4,
        fps=30
    )
    controller.run()
