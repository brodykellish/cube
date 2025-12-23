"""
Refactored LED Cube Controller with clean menu navigation and visualization management.

This demonstrates a cleaner architecture that:
- Separates menu navigation from visualization configuration
- Uses structured actions instead of string parsing
- Eliminates special cases and legacy redirects
"""
import time
from pathlib import Path
from typing import Optional, Callable, Dict
import tempfile

from cube.display import Display
from cube.menu.menu_renderer import MenuRenderer
from cube.menu.navigation import MenuNavigator
from cube.menu.actions import (
    MenuAction,
    QuitAction,
    LaunchVisualizationAction,
    MixerAction,
    PromptAction,
    ShaderSelectionAction,
)
from cube.menu.menu_states import MainMenu, VisualizationModeSelect, ShaderBrowser, SettingsMenu
from cube.menu.prompt_menu import PromptMenuState
from cube.render import SurfacePixelMapper, CubePixelMapper
from cube.render.dag_renderer import DAGRenderer
from cube.shader import SphericalCamera
from cube.midi import MIDIState, MIDIKeyboardDriver, MIDIUniformSource, USBMIDIDriver, load_midi_config
from cube.input.input_manager import InputManager
from cube.input.keyboard_source import KeyboardInputSource
from cube.input.midi_source import MIDIInputSource
from cube.input.actions import Action, InputContext
from cube.shader.audio_uniform_mapping_source import AudioUniformMappingSource


class CubeController:
    """
    Main controller with clean separation of concerns.

    The controller handles:
    - Menu navigation (delegated to MenuNavigator)
    - Visualization launching based on structured actions
    - Main run loop
    """

    def __init__(
        self,
        width: int,
        height: int,
        num_panels: int = 6,
        fps: int = 60,
        default_brightness: float = 60.0,
        default_gamma: float = 2.2,
        scale: int = 1,
        **kwargs,
    ):
        """Initialize the controller."""
        self.window_width = width
        self.window_height = height
        self.fps = fps
        self.frame_time = 1.0 / fps
        self.num_panels = num_panels
        self.default_brightness = default_brightness
        self.default_gamma = default_gamma
        self.display = Display(width, height, num_layers=3, scale=scale, **kwargs)
        self.width = self.display.width
        self.height = self.display.height
        
        if self.num_panels == 1:
            self.panel_width = self.width
            self.panel_height = self.height
        else:
            self.panel_width = self.width // self.num_panels
            self.panel_height = self.height
        
        self.menu_layer = self.display.get_layer(0)
        self.shader_layer = self.display.get_layer(1)
        self.debug_layer = self.display.get_layer(2)
        self.settings = {
            "debug_ui": False,
            "debug_axes": False,
            "brightness": default_brightness,
            "gamma": default_gamma,
            "fps_limit": fps,
        }

        # Unified input manager (keyboard + MIDI → actions/axes)
        self.input_manager = InputManager()

        # MIDI subsystem (must be initialized before wiring input sources)
        self.midi_state = MIDIState(num_channels=7)
        self.midi_keyboard = MIDIKeyboardDriver(self.midi_state)
        self.midi_config = load_midi_config()
        self.usb_midi = None
        self.last_bpm = None
        
        if self.midi_config:
            self.usb_midi = USBMIDIDriver(self.midi_state, self.midi_config, tap_note=43)
            if self.usb_midi.is_connected():
                print(f'USB MIDI controller connected: {self.usb_midi.connected_device}')
                print('  Tap tempo: Pad 8 (Note 43)')
        else:
            print('No MIDI config found (midi_config.yml) - USB MIDI disabled')
        
        tap_tempo = self.usb_midi.tap_tempo if self.usb_midi else None
        self.midi_uniform_source = MIDIUniformSource(self.midi_state, tap_tempo)

        # Now that MIDI state exists, wire input sources into InputManager
        self._configure_input_sources()
        self.input_manager.set_context(InputContext.MENU)

        self.menu_renderer = MenuRenderer(self.menu_layer)
        self.menu_navigator = MenuNavigator(self.width, self.height, self.settings)
        self._register_menus()
        
        self.gamepad = None
        try:
            if hasattr(self.display.backend, 'pygame'):
                from cube.input.gamepad import GamepadCameraInput
                self.gamepad = GamepadCameraInput(self.display.backend.pygame, joystick_index=0)
                if not self.gamepad.is_connected():
                    self.gamepad = None
        except Exception:
            pass
        
        # DAG-based renderer and current visualization state
        self.renderer: Optional[DAGRenderer] = None
        self.current_shader_path = None
        self.is_visualizing = False
        self.launched_from_prompt = False
        self.fps_counter = 0
        self.fps_last_time = time.time()
        self.fps_current = 0.0
        self._cleanup_done = False

        # Debug waveform history for beat visualization
        self._beat_history: list[tuple[float, float]] = []

        # Action handlers for visualization settings/effects
        self._action_handlers: Dict[Action, Callable[[], None]] = {}
        self._register_action_handlers()

    # ------------------------------------------------------------------
    # Input wiring
    # ------------------------------------------------------------------
    def _configure_input_sources(self) -> None:
        """Register keyboard and MIDI sources with the InputManager."""
        # Keyboard source from display backend
        keyboard_driver = None
        backend = getattr(self.display, "backend", None)
        if backend is not None:
            # Pygame backend exposes .pygame and uses PygameKeyboard internally.
            if hasattr(backend, "keyboard"):
                keyboard_driver = backend.keyboard

        if keyboard_driver is None:
            # Fallback: no keyboard driver exposed; controller can't drive input.
            # Keep InputManager but without a keyboard source.
            pass
        else:
            self.input_manager.register_source(KeyboardInputSource(keyboard_driver))

        # MIDI source (optional but preferred)
        self.midi_input_source = MIDIInputSource(self.midi_state)
        self.input_manager.register_source(self.midi_input_source)

    def _register_action_handlers(self) -> None:
        """Register handlers for high-level actions during visualization."""

        def toggle_debug() -> None:
            self.settings["debug_ui"] = not self.settings.get("debug_ui", False)
            status = "enabled" if self.settings["debug_ui"] else "disabled"
            print(f"Debug UI {status}")

        def inc_brightness() -> None:
            self.settings["brightness"] = min(
                100.0, self.settings.get("brightness", self.default_brightness) + 5.0
            )
            print(f"Brightness: {self.settings['brightness']:.0f}%")

        def dec_brightness() -> None:
            self.settings["brightness"] = max(
                1.0, self.settings.get("brightness", self.default_brightness) - 5.0
            )
            print(f"Brightness: {self.settings['brightness']:.0f}%")

        def inc_gamma() -> None:
            self.settings["gamma"] = min(
                3.0, self.settings.get("gamma", self.default_gamma) + 0.1
            )
            print(f"Gamma: {self.settings['gamma']:.2f}")

        def dec_gamma() -> None:
            self.settings["gamma"] = max(
                0.5, self.settings.get("gamma", self.default_gamma) - 0.1
            )
            print(f"Gamma: {self.settings['gamma']:.2f}")

        def inc_fps() -> None:
            self.settings["fps_limit"] = min(
                120, self.settings.get("fps_limit", self.fps) + 5
            )
            print(f"FPS Limit: {self.settings['fps_limit']}")

        def dec_fps() -> None:
            self.settings["fps_limit"] = max(
                10, self.settings.get("fps_limit", self.fps) - 5
            )
            print(f"FPS Limit: {self.settings['fps_limit']}")

        def reload_shader() -> None:
            if self.current_shader_path and self.renderer:
                print(f"Reloading shader: {self.current_shader_path}")
                try:
                    self.renderer.load_shader(str(self.current_shader_path))
                except Exception as exc:
                    print(f"Error reloading shader: {exc}")

        def undo_effect() -> None:
            if self.renderer and hasattr(self.renderer, "effect_manager"):
                self.renderer.effect_manager.undo_effect()

        def redo_effect() -> None:
            if self.renderer and hasattr(self.renderer, "effect_manager"):
                self.renderer.effect_manager.redo_effect()

        self._action_handlers = {
            Action.TOGGLE_DEBUG: toggle_debug,
            Action.INCREASE_BRIGHTNESS: inc_brightness,
            Action.DECREASE_BRIGHTNESS: dec_brightness,
            Action.INCREASE_GAMMA: inc_gamma,
            Action.DECREASE_GAMMA: dec_gamma,
            Action.INCREASE_FPS: inc_fps,
            Action.DECREASE_FPS: dec_fps,
            Action.RELOAD_SHADER: reload_shader,
            Action.UNDO_EFFECT: undo_effect,
            Action.REDO_EFFECT: redo_effect,
        }

    def _register_menus(self):
        """Register all menu states with the navigator."""
        self.menu_navigator.register_menu('main', MainMenu())
        self.menu_navigator.register_menu('visualize', VisualizationModeSelect())
        self.menu_navigator.register_menu('surface_browser', ShaderBrowser('surface'))
        self.menu_navigator.register_menu('cube_browser', ShaderBrowser('cube'))
        self.menu_navigator.register_menu('settings', SettingsMenu())
        shaders_dir = Path(__file__).parent.parent.parent / 'shaders'
        self.menu_navigator.register_menu('prompt', PromptMenuState(self.width, self.height, shaders_dir))
        self.menu_navigator.navigate_to('main')

    def run(self):
        """Main game loop: poll input, resolve actions, and render."""
        print("\nStarting cube controller...")
        print("Controls: Arrow keys to navigate, Enter to select, ESC to back/exit")

        running = True
        last_frame_time = time.time()
        
        while running:
            frame_start = time.time()
            dt = frame_start - last_frame_time
            last_frame_time = frame_start
            
            # Poll low-level events and feed into unified InputManager
            events = self.display.handle_events()
            # The display backend keyboard already feeds its own state; we only
            # need quit/paste from events here. InputManager gets full state
            # from its InputSource wrappers.
            self.input_manager.poll()
            
            if self.input_manager.is_quit_requested() or events.get("quit"):
                running = False
            else:
                if self.is_visualizing:
                    running = self._update_visualization(dt)
                else:
                    running = self._update_menu(dt)

                # MIDI tempo diagnostics (visualization mode only)
                if self.is_visualizing and self.usb_midi:
                    current_bpm = self.usb_midi.tap_tempo.get_bpm()
                    if current_bpm != self.last_bpm:
                        if current_bpm is not None:
                            print(f"🎵 Tempo detected: {current_bpm:.1f} BPM")
                        else:
                            print("⏸  Tempo timeout")
                        self.last_bpm = current_bpm
                
                # Render current mode
                if self.is_visualizing:
                    self._render_visualization()
                else:
                    self._render_menu()
                
                # FPS accounting and sleep
                self.fps_counter += 1
                current_time = time.time()
                if current_time - self.fps_last_time >= 1.0:
                    self.fps_current = self.fps_counter / (current_time - self.fps_last_time)
                    self.fps_counter = 0
                    self.fps_last_time = current_time
                
                frame_time = time.time() - frame_start
                target_fps = self.settings.get("fps_limit", self.fps)
                if target_fps and target_fps > 0:
                    sleep_time = 1.0 / target_fps - frame_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)
        
        print("Shutdown complete")
        self.cleanup()

    # ------------------------------------------------------------------
    # Per-mode updates
    # ------------------------------------------------------------------
    def _update_menu(self, dt: float) -> bool:
        """Process input and menu navigation in MENU context."""
        self.input_manager.set_context(InputContext.MENU)

        # Handle menu-scoped actions (e.g. toggle debug)
        pressed_actions = self.input_manager.get_pressed_actions()
        held_actions = self.input_manager.get_held_actions()
        if Action.TOGGLE_DEBUG in pressed_actions:
            handler = self._action_handlers.get(Action.TOGGLE_DEBUG)
            if handler:
                handler()

        # Map high-level navigation actions to legacy menu key strings
        key_for_action = None
        if self.input_manager.is_action_pressed(Action.NAVIGATE_UP):
            key_for_action = "up"
        elif self.input_manager.is_action_pressed(Action.NAVIGATE_DOWN):
            key_for_action = "down"
        elif self.input_manager.is_action_pressed(Action.NAVIGATE_LEFT):
            key_for_action = "left"
        elif self.input_manager.is_action_pressed(Action.NAVIGATE_RIGHT):
            key_for_action = "right"
        elif self.input_manager.is_action_pressed(Action.CONFIRM):
            key_for_action = "enter"
        elif self.input_manager.is_action_pressed(Action.BACK) or self.input_manager.is_action_pressed(
            Action.CANCEL
        ):
            key_for_action = "escape"

        if key_for_action:
            action = self.menu_navigator.handle_input(key_for_action)
            if action:
                return self._handle_action(action)

        paste_text = self.input_manager.get_paste_text()
        if paste_text and hasattr(self.menu_navigator.current_state, "handle_paste"):
            self.menu_navigator.current_state.handle_paste(paste_text)

        action = self.menu_navigator.update(dt)
        if action:
            return self._handle_action(action)

        return True

    def _update_visualization(self, dt: float) -> bool:
        """Process input and actions while a visualization is running."""
        self.input_manager.set_context(InputContext.VISUALIZATION)

        # Exit visualization on CANCEL/BACK
        if self.input_manager.is_action_pressed(Action.CANCEL) or self.input_manager.is_action_pressed(
            Action.BACK
        ):
            self._stop_visualization()
            return True

        # Apply any one-shot visualization actions using the state from the main poll
        pressed_actions = self.input_manager.get_pressed_actions()
        held_actions = self.input_manager.get_held_actions()
        for action in pressed_actions:
            # Handle built-in visualization actions (debug, gamma, fps, reload)
            handler = self._action_handlers.get(action)
            if handler:
                handler()
        
        # Effects via manager (toggle and momentary)
        if self.renderer and hasattr(self.renderer, "effect_manager"):
            try:
                self.renderer.effect_manager.process_inputs(pressed_actions, held_actions)
            except Exception as exc:
                print(f"Effect manager error: {exc}")

        # Always update the renderer's parameter source (it consumes pressed/held actions)
        if self.renderer and hasattr(self.renderer, "param_source"):
            try:
                self.renderer.param_source.update(dt)
            except Exception:
                pass

        # Continuous axes (camera, params) are handled inside DAGRenderer via
        # CameraUniformSource + ParameterUniformSource, which read from the
        # shared InputManager each frame.
        self._route_visualization_midi_keys(dt)

        return True

    def cleanup(self):
        """Clean up resources (display, input, etc.)."""
        if self.usb_midi:
            self.usb_midi.cleanup()
        if hasattr(self, 'gamepad') and self.gamepad:
            self.gamepad.cleanup()
        if self._cleanup_done:
            return
        self._cleanup_done = True
        if self.display:
            self.display.cleanup()
        if self.renderer:
            self.renderer.cleanup()

    def _handle_action(self, action: MenuAction) -> bool:
        """
        Handle an action from the menu system.

        Returns:
            True to continue running, False to quit.
        """
        if isinstance(action, QuitAction):
            return False
        if isinstance(action, PromptAction):
            self.menu_navigator.navigate_to('prompt')
            return True
        if isinstance(action, LaunchVisualizationAction):
            self._launch_visualization(action)
            return True
        if isinstance(action, ShaderSelectionAction):
            if action.pixel_mapper:
                launch_action = LaunchVisualizationAction(shader_path=action.shader_path, pixel_mapper=action.pixel_mapper)
                self._launch_visualization(launch_action)
                return True
            print(f'Warning: Shader selected but no pixel mapper specified: {action.shader_path}')
            return True
        if isinstance(action, MixerAction):
            print(f"Mixer action not yet implemented: {action}")
            return True
        return True

    def _launch_visualization(self, action: LaunchVisualizationAction):
        """Launch a visualization based on the action configuration."""
        self.launched_from_prompt = self.menu_navigator.current_state.name == 'prompt'
        print(f"\n{'============================================================'}")
        print("Launching visualization")
        print(f"Pixel mapper: {action.pixel_mapper}")
        shader_path = action.shader_path
        print(f"Shader: {shader_path}")
        print(f"{'============================================================'}")
        print("Controls:")
        print("  WASD: Rotate view")
        print("  Shift+WS: Zoom in/out")
        print("  Shift+AD: Roll left/right")
        if self.gamepad and self.gamepad.is_connected():
            print("\nGamepad:")
            print("  Left Stick: Rotate camera")
            print("  Right Stick Y: Zoom in/out")
        print("\nSettings:")
        print("  B/V: Brightness -/+")
        print("  F/G: Gamma -/+")
        print("  -/=: FPS Limit -/+")
        print("\nActions:")
        print("  R: Reload shader")
        print("  I: Toggle debug info")
        print("  ESC: Return to menu")
        print("\nMIDI Parameters:")
        print("  n/m: CC0 (param0) -/+")
        print("  ,/. : CC1 (param1) -/+")
        print("  [/] : CC2 (param2) -/+")
        print("  ;/' : CC3 (param3) -/+")
        
        try:
            if action.pixel_mapper == "surface":
                camera = SphericalCamera()
                pixel_mapper = SurfacePixelMapper(self.width, self.height, camera)
            elif action.pixel_mapper == "cube":
                print(f"Cube panel dimensions: {self.panel_width}×{self.panel_height}")
                print(f"Cube num panels: {self.num_panels}")
                pixel_mapper = CubePixelMapper(face_width=self.panel_width, face_height=self.panel_height, num_panels=self.num_panels)
            else:
                raise ValueError(f'Unknown pixel mapper: {action.pixel_mapper}')
            
            if self.renderer:
                self.renderer.cleanup()
            
            # Audio mapping for parameters (optional)
            audio_mapping_source = None
            try:
                from cube.audio.shared_state import AudioStateReader

                audio_mapping_source = AudioUniformMappingSource(AudioStateReader())
            except Exception:
                audio_mapping_source = None

            self.renderer = DAGRenderer(
                pixel_mapper=pixel_mapper,
                input_manager=self.input_manager,
                settings=self.settings,
                uniform_sources=[self.midi_uniform_source],
                audio_mapping_source=audio_mapping_source,
            )
            self.renderer.load_shader(str(shader_path))
            self.current_shader_path = shader_path
            self.is_visualizing = True
            print("Visualization started. Press ESC to return to menu.")
        except Exception as e:
            print(f"Error launching visualization: {e}")
            import traceback
            traceback.print_exc()
            self.is_visualizing = False
            return

    def _stop_visualization(self):
        """Stop current visualization and return to menu."""
        if self.launched_from_prompt:
            print("Returning to prompt...")
            self.menu_navigator.navigate_to("prompt")
        else:
            print("Returning to menu...")
        
        if self.renderer:
            self.renderer.cleanup()
            self.renderer = None
        self.is_visualizing = False
        self.current_shader_path = None
        self.launched_from_prompt = False

    def _route_visualization_midi_keys(self, dt: float) -> None:
        """
        Route held keys through MIDIKeyboardDriver for smooth CC updates.

        This keeps keyboard→MIDI mappings working on top of the InputManager
        axis system (e.g. n/m, ,/. for params).
        """
        # Build a synthetic held-keys list from current keyboard InputSource.
        held_keys: list[str] = []
        # KeyboardInputSource encodes keys as 'key:NAME' in InputState. Bindings
        # map those to Actions/Axes, but for MIDIKeyboardDriver we only care
        # about the logical key names.
        # We approximate this by using the current bindings for param actions.
        # For now, we leave MIDIKeyboardDriver mostly for discrete taps; smooth
        # param control is handled via axes in ParameterUniformSource.
        self.midi_keyboard.update_from_held_keys(held_keys, dt)

    def _reload_shader(self):
        """Reload current shader."""
        if self.unified_renderer and self.current_shader_path:
            print(f'Reloading shader: {self.current_shader_path}')
            try:
                self.unified_renderer.load_shader(str(self.current_shader_path))
            except Exception as e:
                print(f'Error reloading shader: {e}')

    def _render_debug_overlay(self):
        """Render debug information (FPS, camera position, params, waveform) to debug layer."""
        import numpy as np

        self.debug_layer[:, :, :] = 0

        # Always render active effects list (top-left) for quick visibility.
        self._render_effect_overlay()
        
        if not self.settings.get('debug_ui', False):
            return
        
        from cube.menu.menu_renderer import MenuRenderer

        debug_renderer = MenuRenderer(self.debug_layer)
        height, width = self.debug_layer.shape[:2]
        char_width = 4
        char_height = 8
        line_spacing = 2
        lines: list[str] = []
        
        # Line 1: FPS
        fps_text = f'FPS: {self.fps_current:.1f}'
        lines.append(fps_text)
        
        # Line 2: Camera position (if available)
        if self.is_visualizing and self.renderer:
            try:
                camera_source = self.renderer.get_camera_source()
                camera_uniforms = camera_source.get_uniforms()
                cam_pos = camera_uniforms.get('iCameraPos', (0.0, 0.0, 0.0))
                cam_text = f'Cam: ({cam_pos[0]:.1f},{cam_pos[1]:.1f},{cam_pos[2]:.1f})'
                lines.append(cam_text)
            except Exception:
                pass
        
        # Line 3: Parameters iParam0-7 from renderer state
        params = None
        beat_phase = 0.0
        beat_pulse = 0.0
        if self.is_visualizing and self.renderer:
            try:
                debug_state = self.renderer.get_debug_state()
                params = debug_state.get('params')
                beat_phase = float(debug_state.get('beat_phase', 0.0))
                beat_pulse = float(debug_state.get('beat_pulse', 0.0))
            except Exception:
                params = None
        param_line_start = None
        if params is not None:
            param_line_start = len(lines)
            first_row = ' '.join(f'{p:.2f}' for p in params[:4])
            second_row = ' '.join(f'{p:.2f}' for p in params[4:])
            lines.append(f'{first_row}')
            lines.append(f'{second_row}')
        
        # Layout text in top-right corner
        max_text_len = max((len(line) for line in lines)) if lines else 0
        text_width = max_text_len * char_width
        x_pos = width - text_width - 2
        y_start = height - len(lines) * (char_height + line_spacing) - 2
        
        for i, line in enumerate(lines):
            y_pos = y_start + i * (char_height + line_spacing)
            if i == 0:
                color = (0, 255, 0)
            elif line.startswith('Cam:'):
                color = (100, 200, 255)
            elif param_line_start is not None and i >= param_line_start:
                color = (255, 255, 0)  # brighter yellow for params
            else:
                color = (200, 200, 200)
            debug_renderer.draw_text(line, x_pos, y_pos, color=color, scale=1)

        # Waveform visualizer in bottom-left for beat pulse/phase
        self._render_beat_waveform(beat_phase, beat_pulse)

    def _render_beat_waveform(self, beat_phase: float, beat_pulse: float) -> None:
        """Render simple waveform visualization for beat phase/pulse in bottom-left."""
        import numpy as np

        height, width = self.debug_layer.shape[:2]
        if width == 0 or height == 0:
            return

        # Append new sample and clamp history
        self._beat_history.append((beat_phase, beat_pulse))
        max_samples = min(width // 2, 128)
        if len(self._beat_history) > max_samples:
            self._beat_history = self._beat_history[-max_samples:]

        wave_width = len(self._beat_history)
        wave_height = min(32, height // 4)
        y_start = height - wave_height
        x_start = 0

        # Clear region
        self.debug_layer[y_start:height, x_start:x_start + wave_width, :] = 0

        if wave_width <= 1:
            return

        # Split the band: top half = phase (green), bottom half = pulse (pink)
        # Leave a 1px spacer between the two bands
        spacer = 1
        phase_height = wave_height // 2
        pulse_height = wave_height - phase_height - spacer
        phase_base = y_start + phase_height - 1  # bottom of phase band
        pulse_base = y_start + wave_height - 1   # bottom of pulse band

        for i, (phase, pulse) in enumerate(self._beat_history):
            x = x_start + i
            if x < 0 or x >= width:
                continue
            clamped_phase = max(0.0, min(1.0, phase))
            clamped_pulse = max(0.0, min(1.0, pulse))

            # Phase column (green)
            phase_fill = int(clamped_phase * (phase_height - 1))
            y_phase_top = max(0, phase_base - phase_fill)
            y_phase_bottom = phase_base
            self.debug_layer[y_phase_top:y_phase_bottom + 1, x, 0] = 0
            self.debug_layer[y_phase_top:y_phase_bottom + 1, x, 1] = 255
            self.debug_layer[y_phase_top:y_phase_bottom + 1, x, 2] = 0

            # Pulse column (pink)
            pulse_fill = int(clamped_pulse * (pulse_height - 1))
            y_pulse_top = max(0, pulse_base - pulse_fill)
            y_pulse_bottom = pulse_base
            self.debug_layer[y_pulse_top:y_pulse_bottom + 1, x, 0] = 255
            self.debug_layer[y_pulse_top:y_pulse_bottom + 1, x, 1] = 105
            self.debug_layer[y_pulse_top:y_pulse_bottom + 1, x, 2] = 180

        # Labels at left edge
        label_color_phase = (0, 255, 0)
        label_color_pulse = (255, 105, 180)
        try:
            from cube.menu.menu_renderer import MenuRenderer
            label_renderer = MenuRenderer(self.debug_layer)
            label_renderer.draw_text("phase", x_start + 2, y_start, color=label_color_phase, scale=1)
            label_renderer.draw_text("pulse", x_start + 2, y_start + phase_height + spacer, color=label_color_pulse, scale=1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Effect overlay
    # ------------------------------------------------------------------
    def _format_binding_label(self, raw_input: tuple[str]) -> str:
        """Format a raw binding tuple for display."""
        parts = []
        for key in raw_input:
            if key.startswith("key:"):
                parts.append(key.split("key:", 1)[1])
            elif key.startswith("midi:"):
                parts.append(key.split("midi:", 1)[1])
            else:
                parts.append(key)
        return "+".join(parts)

    def _render_effect_overlay(self) -> None:
        """Render active effects and their deactivation bindings in top-left."""
        if not self.renderer or not hasattr(self.renderer, "effect_manager"):
            return
        try:
            active_actions = self.renderer.effect_manager.get_active_actions()
        except Exception:
            return
        if not active_actions:
            return

        from cube.menu.menu_renderer import MenuRenderer

        lines: list[str] = []
        for action in active_actions:
            friendly = action.name.replace("TOGGLE_", "").replace("_", " ").title()
            raw_bindings = self.input_manager.bindings.get_raw_inputs(
                action, InputContext.VISUALIZATION
            )
            labels = [self._format_binding_label(b) for b in raw_bindings] if raw_bindings else []
            binding_text = ", ".join(labels) if labels else "[unbound]"
            lines.append(f"{friendly}: {binding_text}")

        if not lines:
            return

        overlay_renderer = MenuRenderer(self.debug_layer)
        char_height = 8
        line_spacing = 2
        x_pos = 2
        y_start = 2
        for i, line in enumerate(lines):
            y_pos = y_start + i * (char_height + line_spacing)
            overlay_renderer.draw_text(line, x_pos, y_pos, color=(255, 255, 255), scale=1)

    def _render_menu(self):
        """Render current menu."""
        self.shader_layer[:, :, :] = 0
        self.menu_layer[:, :, :] = 0
        self.menu_navigator.render(self.menu_renderer)
        self._render_debug_overlay()
        self.display.show(brightness=self.settings.get('brightness', 90.0), gamma=self.settings.get('gamma', 1.0))

    def _render_visualization(self):
        """Render current visualization."""
        if not self.renderer:
            return

        # Let pixel mapper react to current camera vectors if it supports it.
        if hasattr(self.renderer.pixel_mapper, 'update_from_camera'):
            try:
                camera_uniforms = self.renderer.get_camera_source().get_uniforms()
                self.renderer.pixel_mapper.update_from_camera(camera_uniforms)
            except Exception:
                pass

        self.menu_layer[:, :, :] = 0
        framebuffer = self.renderer.render()
        fb_height, fb_width = framebuffer.shape[:2]
        layer_height, layer_width = self.shader_layer.shape[:2]

        if fb_height == layer_height and fb_width == layer_width:
            self.shader_layer[:] = framebuffer
        else:
            self.shader_layer[:, :, :] = 0
            y_offset = (layer_height - fb_height) // 2
            x_offset = (layer_width - fb_width) // 2
            self.shader_layer[y_offset:y_offset + fb_height, x_offset:x_offset + fb_width] = framebuffer

        self._render_debug_overlay()
        self.display.show(
            brightness=self.settings.get('brightness', 90.0),
            gamma=self.settings.get('gamma', 1.0),
        )

