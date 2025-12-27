"""
VisualizationRunner - Manages visualization in a separate thread.

Keeps the renderer alive and handles pipeline deployment.
"""
import queue
import threading
import time
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import numpy as np

from cube.display.visualization_window import VisualizationWindow
from cube.render.dag_renderer import DAGRenderer
from cube.render.pixel_mappers import SurfacePixelMapper, CubePixelMapper
from cube.shader import SphericalCamera
from cube.input.input_manager import InputManager
from cube.input.actions import Action, Axis
from cube.input.midi_source import MIDIInputSource
from cube.dag.dag import DAG
from cube.dag.source_node import SourceNode


class VisualizationRunner:
    """
    Manages visualization rendering in a separate thread.
    
    Keeps renderer alive between pipeline swaps, allowing parameters/effects to persist.
    """
    
    def __init__(self, width: int, height: int, num_panels: int = 6,
                 midi_state=None, midi_uniform_source=None,
                 settings: Optional[Dict[str, Any]] = None,
                 viz_window: Optional[VisualizationWindow] = None,
                 stop_callback: Optional[Callable[[], None]] = None,
                 framebuffer_queue: Optional[queue.Queue] = None):
        """
        Initialize visualization runner.
        
        CRITICAL: viz_window must be created on main thread (macOS requirement).
        
        Args:
            width: Window width in pixels
            height: Window height in pixels
            num_panels: Number of cube panels (for cube pixel mapper)
            midi_state: MIDIState instance for MIDI input
            midi_uniform_source: MIDIUniformSource for uniform mapping
            settings: Settings dictionary for renderer
            viz_window: VisualizationWindow instance (created on main thread)
            stop_callback: Optional callback to signal stop from visualization thread
        """
        # Store config for thread to use
        self._width = width
        self._height = height
        self._num_panels = num_panels
        self._midi_state = midi_state
        self._midi_uniform_source = midi_uniform_source
        self._settings = settings or {}
        self._viz_window = viz_window  # Window created on main thread
        self._stop_callback = stop_callback  # Callback to signal stop
        
        # Calculate panel dimensions
        if num_panels == 1:
            self._panel_width = width
            self._panel_height = height
        else:
            self._panel_width = width // num_panels
            self._panel_height = height
        
        # Thread-safe communication
        self._pipeline_queue = queue.Queue()
        self._framebuffer_queue = framebuffer_queue  # Queue to send rendered frames to controller
        self._save_config_queue = queue.Queue()  # Queue for save DAG config requests
        self._load_config_queue = queue.Queue()  # Queue for load DAG config requests
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # These will be created in visualization thread
        self._renderer: Optional[DAGRenderer] = None
        self._viz_input_manager: Optional[InputManager] = None
        self._current_shader_path: Optional[Path] = None
        self._action_handlers: Dict[Action, Callable[[], None]] = {}
        self._fps_current: float = 0.0
        self._fps_last_time: float = time.time()
        self._fps_frame_count: int = 0
        self._debug_layer: Optional[np.ndarray] = None  # Separate debug layer
    
    def start(self):
        """Launch visualization thread (non-blocking)."""
        if self._thread is not None:
            return  # Already started
        
        self._thread = threading.Thread(
            target=self._run_loop,
            name="VisualizationThread",
            daemon=True
        )
        self._thread.start()
        print("[MAIN] Visualization thread started")
    
    def _run_loop(self):
        """
        Main visualization thread loop.
        
        CRITICAL: Window is created on main thread (macOS requirement).
        This thread uses the window's OpenGL context for rendering.
        """
        try:
            if not self._viz_window:
                print("[VIZ] Error: Visualization window not provided")
                return
            
            print("[VIZ] Initializing visualization renderer...")
            
            # Make the window's context current in this thread
            # The window was created on main thread, but we can use its context here
            self._viz_window.backend.window.switch_to()
            
            # Use the window's input manager (window owns it)
            self._viz_input_manager = self._viz_window.input_manager
            
            # Register MIDI source (always active, regardless of focus)
            if self._midi_state:
                self._viz_input_manager.register_source(MIDIInputSource(self._midi_state))
            
            # Create default pixel mapper (surface)
            camera = SphericalCamera()
            pixel_mapper = SurfacePixelMapper(self._width, self._height, camera)
            
            # Audio mapping for parameters (optional)
            audio_mapping_source = None
            try:
                from cube.audio.shared_state import AudioStateReader
                from cube.shader.audio_uniform_mapping_source import AudioUniformMappingSource
                audio_mapping_source = AudioUniformMappingSource(AudioStateReader())
            except Exception:
                pass
            
            # Create ParameterStore and HandlerRegistry
            print("[VIZ] Creating parameter store and handlers...")
            from cube.render.parameter_store import (
                ParameterStore, ParameterHandlerRegistry,
                TimeHandler, CameraHandler, MouseHandler,
                SignalParameterHandler, DirectParameterHandler,
                SettingsParameterHandler
            )
            from cube.core.signals import KeyboardParamSignal, AudioSignal
            from cube.input.actions import Action
            
            parameter_store = ParameterStore(settings=self._settings)
            handler_registry = ParameterHandlerRegistry()
            
            # Create and register time handler
            time_handler = TimeHandler(parameter_store)
            handler_registry.register(time_handler)
            
            # Create and register camera handler
            camera_handler = CameraHandler(parameter_store, camera, self._viz_input_manager)
            handler_registry.register(camera_handler)
            
            # Create and register mouse handler
            mouse_handler = MouseHandler(parameter_store, self._width, self._height)
            handler_registry.register(mouse_handler)
            
            # Store references for debug access
            self._parameter_store = parameter_store
            self._camera_handler = camera_handler
            self._mouse_handler = mouse_handler
            
            # Create signal-based handlers for iParam0-7 (keyboard increment/decrement)
            # Store all handlers so we can enable/disable them dynamically
            param_handlers = {}  # param_id -> {keyboard, midi, audio}
            for i in range(8):
                param_id = f'iParam{i}'
                param_axis = getattr(Axis, f'PARAM{i}')
                inc_action = getattr(Action, f'INC_PARAM{i}')
                dec_action = getattr(Action, f'DEC_PARAM{i}')
                
                # Keyboard signal handler (low priority - can be overridden)
                keyboard_signal = KeyboardParamSignal(self._viz_input_manager, param_axis, inc_action, dec_action)
                keyboard_handler = SignalParameterHandler(
                    parameter_store,
                    keyboard_signal,
                    param_id,
                    priority=0  # Low priority
                )
                handler_registry.register(keyboard_handler)
                
                # MIDI direct handler (high priority - overrides keyboard)
                midi_handler = DirectParameterHandler(
                    parameter_store,
                    self._viz_input_manager,
                    param_id,
                    param_axis,
                    priority=100  # High priority - overrides keyboard
                )
                handler_registry.register(midi_handler)
                
                # Audio signal handler (created for all params, enabled/disabled based on mapping)
                audio_handler = None
                audio_signal = None
                if audio_mapping_source:
                    # Create audio signal handler (will be configured based on mapping)
                    # We'll use a placeholder signal initially, but update it when mappings change
                    audio_signal = AudioSignal(audio_mapping_source, '')  # Empty initially
                    audio_handler = SignalParameterHandler(
                            parameter_store,
                            audio_signal,
                            param_id,
                            priority=200  # Highest priority - overrides MIDI and keyboard
                        )
                    handler_registry.register(audio_handler)
                    # Initially disabled - will be enabled when mapping exists
                    audio_handler.set_enabled(False)
                
                param_handlers[param_id] = {
                    'keyboard': keyboard_handler,
                    'midi': midi_handler,
                    'audio': audio_handler,
                    'audio_signal': audio_signal,  # Store signal reference for updates
                }
            
            # Store handlers for dynamic updates
            self._param_handlers = param_handlers
            self._last_audio_mappings = {}
            self._audio_mapping_check_accumulator = 0.0
            self._audio_mapping_check_interval = 0.5  # Check every 0.5 seconds
            
            # Initialize handler states based on current mappings
            if audio_mapping_source:
                self._update_parameter_handlers_from_mappings(audio_mapping_source)
            
            # Create iSeed handler (direct from InputManager)
            seed_handler = DirectParameterHandler(
                parameter_store,
                self._viz_input_manager,
                'iSeed',
                Axis.SEED,
                priority=0
            )
            handler_registry.register(seed_handler)
            
            # Create beat parameter handlers (from audio)
            if audio_mapping_source:
                beat_pulse_signal = AudioSignal(audio_mapping_source, 'u_audio_beat_pulse')
                beat_pulse_handler = SignalParameterHandler(
                    parameter_store,
                    beat_pulse_signal,
                    'iBeatPulse',
                    priority=0
                )
                handler_registry.register(beat_pulse_handler)
                
                beat_phase_signal = AudioSignal(audio_mapping_source, 'u_audio_beat_phase')
                beat_phase_handler = SignalParameterHandler(
                    parameter_store,
                    beat_phase_signal,
                    'iBeatPhase',
                    priority=0
                )
                handler_registry.register(beat_phase_handler)
            
            # Create iDebugAxes handler (from settings)
            debug_axes_handler = SettingsParameterHandler(
                parameter_store,
                self._settings,
                'iDebugAxes',
                'debug_axes',
                transform=lambda x: 1.0 if x else 0.0,
                priority=0
            )
            handler_registry.register(debug_axes_handler)
            
            print("[VIZ] Parameter handlers registered")
            
            # Create renderer (uses OpenGL context from pyglet window)
            print("[VIZ] Creating DAG renderer...")
            
            # Use visualization window's context instead of creating ShaderRenderer
            def make_context_current():
                """Make visualization window's context current."""
                try:
                    self._viz_window.backend.window.switch_to()
                    return True
                except Exception as e:
                    print(f"[VIZ] Error making context current: {e}")
                    return False
            
            self._renderer = DAGRenderer(
                pixel_mapper=pixel_mapper,
                make_context_current=make_context_current,
            )
            print("[VIZ] DAG renderer created")
            
            # Store parameter store and handler registry for use in render loop
            self._parameter_store = parameter_store
            self._handler_registry = handler_registry
            self._audio_mapping_source = audio_mapping_source
            self._mouse_handler = mouse_handler
            
            # Create DAG (maintained as state in visualization runner)
            self._dag: DAG = DAG()
            
            # Create effect manager (needs renderer for VAO and GLSL version)
            from cube.render.effect_manager import EffectManager
            from cube.render.effect_config_loader import load_effect_config
            self._effect_manager = EffectManager(self._renderer)
            
            # Load effects from config file
            effect_definitions = load_effect_config()
            for effect_def in effect_definitions:
                self._effect_manager.add_effect(
                    effect_def.action,
                    effect_def.shader_path,
                    effect_def.trigger_mode,
                    effect_def.node_class,
                    effect_def.priority
                )
            
            # Create debug layer (same size as render framebuffer)
            self._debug_layer = np.zeros((self._height, self._width, 3), dtype=np.uint8)
            print("[VIZ] Debug layer created")
            
            # Register action handlers
            self._register_action_handlers()
            
            # Main render loop
            print("[VIZ] Starting render loop...")
            while not self._stop_flag.is_set():
                # Check if window is closed
                if not self._viz_window or not self._viz_window.is_focused():
                    print("[VIZ] Window closed, exiting render loop...")
                    self._stop_flag.set()
                    break
                
                loop_start = time.time()
                
                # Get current FPS limit (may be updated by action handlers)
                target_fps = self._settings.get('fps_limit', 60)
                frame_time = 1.0 / target_fps
                
                # Make context current (required before any OpenGL calls)
                try:
                    self._viz_window.backend.window.switch_to()
                except Exception as e:
                    print(f"[VIZ] Error switching to window context: {e}")
                    self._stop_flag.set()
                    break
                
                # Note: Event polling is handled on main thread for macOS compatibility
                # (dispatch_events() must be called from main thread on macOS)
                # We just render here
                
                # Update visualization input (keyboard + MIDI)
                # Keyboard state is updated from main thread's event polling
                # Poll and process input if visualization window is focused OR input forwarding is enabled
                should_poll_input = (
                    (self._viz_window and self._viz_window.is_focused()) or
                    getattr(self, '_input_forwarding_enabled', False)
                )
                
                if should_poll_input:
                    self._viz_input_manager.poll()
                    
                    # Process actions (effects, debug toggle, settings, etc.)
                    self._process_actions()
                # else: Window not focused and forwarding disabled, skip input processing
                
                # Update binding map to check for effect bindings config changes
                # (works even when window is not focused, to allow live remapping)
                if self._viz_input_manager:
                    dt = frame_time  # Approximate delta time
                    if hasattr(self._viz_input_manager.bindings, 'update'):
                        self._viz_input_manager.bindings.update(dt)
                
                # Update mouse handler from window backend
                if hasattr(self, '_mouse_handler') and self._viz_window:
                    backend = self._viz_window.backend
                    if hasattr(backend, 'mouse_x') and hasattr(backend, 'mouse_y') and hasattr(backend, 'mouse_button_pressed'):
                        # Normalize mouse coordinates to 0.0-1.0 range
                        mouse_x_norm = backend.mouse_x / self._width if self._width > 0 else 0.0
                        mouse_y_norm = backend.mouse_y / self._height if self._height > 0 else 0.0
                        self._mouse_handler.set_position(mouse_x_norm, mouse_y_norm)
                        self._mouse_handler.set_button(backend.mouse_button_pressed)
                
                # Update audio mapping source (if needed)
                if hasattr(self, '_audio_mapping_source') and self._audio_mapping_source:
                    self._audio_mapping_source.update(dt)
                    
                    # Periodically check for mapping changes and update handlers
                    self._audio_mapping_check_accumulator += dt
                    if self._audio_mapping_check_accumulator >= self._audio_mapping_check_interval:
                        self._audio_mapping_check_accumulator = 0.0
                        self._update_parameter_handlers_from_mappings(self._audio_mapping_source)
                
                # Update all parameters via handler registry
                if hasattr(self, '_handler_registry'):
                    self._handler_registry.update_all(dt)
                
                # Check pipeline deployment queue
                try:
                    config = self._pipeline_queue.get_nowait()
                    print("config: ", config)
                    self._deploy_pipeline_internal(config)
                except queue.Empty:
                    pass
                
                # Check save config queue
                try:
                    save_request = self._save_config_queue.get_nowait()
                    self._save_dag_config_internal(save_request)
                except queue.Empty:
                    pass
                
                # Check load config queue
                try:
                    load_request = self._load_config_queue.get_nowait()
                    self._load_dag_config_internal(load_request)
                except queue.Empty:
                    pass
                
                # Render frame (only if DAG has nodes)
                has_dag = self._dag and len(self._dag.nodes) > 0
                
                if has_dag:
                    # Skip rendering during fullscreen transitions to avoid OpenGL/Metal errors
                    backend = self._viz_window.backend if self._viz_window else None
                    if backend and getattr(backend, '_fullscreen_transitioning', False):
                        # Skip this frame during transition
                        time.sleep(0.01)  # Small sleep to avoid busy-waiting
                        continue
                    
                    # Ensure context is current before rendering
                    self._renderer.make_context_current()
                    
                    # Render to framebuffer (pass DAG and ParameterStore to renderer)
                    framebuffer = self._renderer.render(self._dag, self._parameter_store)
                    
                    # Update FPS counter (always, for menu debug UI)
                    self._update_fps()
                    
                    # Send framebuffer to controller (non-blocking, drop if queue full)
                    if self._framebuffer_queue is not None:
                        try:
                            # Put a copy of the framebuffer (non-blocking)
                            # If queue is full, drop the frame (controller will get next one)
                            self._framebuffer_queue.put_nowait(framebuffer.copy())
                        except queue.Full:
                            pass  # Drop frame if queue is full
                    
                    # Display to pyglet window (check if window is still valid)
                    if self._viz_window and self._viz_window.is_focused():
                        try:
                            self._viz_window.display(framebuffer)
                        except Exception as e:
                            print(f"[VIZ] Error displaying frame: {e}")
                            # Window might be closed, exit loop
                            self._stop_flag.set()
                            break
                # else: No source nodes loaded yet, skip rendering (will render once pipeline is deployed)
                
                # FPS limit
                elapsed = time.time() - loop_start
                sleep_time = max(0, frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            print("[VIZ] Render loop ended, cleaning up...")
        except Exception as e:
            print(f"[VIZ] Error in visualization thread: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup (still in visualization thread)
            if self._renderer:
                try:
                    self._renderer.cleanup()
                except Exception:
                    pass
            if self._viz_window:
                try:
                    self._viz_window.cleanup()
                except Exception:
                    pass
            print("[VIZ] Visualization thread cleanup complete")
    
    def _update_parameter_handlers_from_mappings(self, audio_mapping_source) -> None:
        """
        Update parameter handlers based on current audio mappings.
        
        Enables/disables keyboard and audio handlers based on whether
        each parameter has an audio mapping.
        
        Args:
            audio_mapping_source: AudioUniformMappingSource instance
        """
        if not hasattr(self, '_param_handlers'):
            return
        
        current_mappings = audio_mapping_source.get_all_mappings()
        
        # Check if mappings have changed
        if current_mappings == self._last_audio_mappings:
            return  # No changes, skip update
        
        self._last_audio_mappings = current_mappings.copy()
        
        # Update handlers for each parameter
        for param_id in range(8):
            param_id_str = f'iParam{param_id}'
            if param_id_str not in self._param_handlers:
                continue
            
            handlers = self._param_handlers[param_id_str]
            keyboard_handler = handlers['keyboard']
            midi_handler = handlers['midi']
            audio_handler = handlers.get('audio')
            audio_signal = handlers.get('audio_signal')
            
            # Check if this parameter has an audio mapping
            audio_signal_name = current_mappings.get(param_id_str)
            
            if audio_signal_name and audio_handler and audio_signal:
                # Parameter is mapped to audio - enable audio handler, disable keyboard
                audio_signal.set_signal_name(audio_signal_name)
                audio_handler.set_enabled(True)
                keyboard_handler.set_enabled(False)
                midi_handler.set_enabled(True)  # MIDI can still override
            else:
                # Parameter is not mapped to audio - enable keyboard, disable audio
                if audio_handler:
                    audio_handler.set_enabled(False)
                keyboard_handler.set_enabled(True)
                midi_handler.set_enabled(True)  # MIDI can still override
    
    def _register_action_handlers(self) -> None:
        """Register handlers for high-level actions during visualization."""
        
        def toggle_debug() -> None:
            self._settings["viz_debug_ui"] = not self._settings.get("viz_debug_ui", False)
            status = "enabled" if self._settings["viz_debug_ui"] else "disabled"
            print(f"[VIZ] Visualization Debug UI {status}")
        
        def inc_brightness() -> None:
            default_brightness = self._settings.get('default_brightness', 60.0)
            self._settings["brightness"] = min(
                100.0, self._settings.get("brightness", default_brightness) + 5.0
            )
            print(f"[VIZ] Brightness: {self._settings['brightness']:.0f}%")
        
        def dec_brightness() -> None:
            default_brightness = self._settings.get('default_brightness', 60.0)
            self._settings["brightness"] = max(
                1.0, self._settings.get("brightness", default_brightness) - 5.0
            )
            print(f"[VIZ] Brightness: {self._settings['brightness']:.0f}%")
        
        def inc_gamma() -> None:
            default_gamma = self._settings.get('default_gamma', 2.2)
            self._settings["gamma"] = min(
                3.0, self._settings.get("gamma", default_gamma) + 0.1
            )
            print(f"[VIZ] Gamma: {self._settings['gamma']:.2f}")
        
        def dec_gamma() -> None:
            default_gamma = self._settings.get('default_gamma', 2.2)
            self._settings["gamma"] = max(
                0.5, self._settings.get("gamma", default_gamma) - 0.1
            )
            print(f"[VIZ] Gamma: {self._settings['gamma']:.2f}")
        
        def inc_fps() -> None:
            default_fps = self._settings.get('fps', 60)
            self._settings["fps_limit"] = min(
                120, self._settings.get("fps_limit", default_fps) + 5
            )
            print(f"[VIZ] FPS Limit: {self._settings['fps_limit']}")
        
        def dec_fps() -> None:
            default_fps = self._settings.get('fps', 60)
            self._settings["fps_limit"] = max(
                10, self._settings.get("fps_limit", default_fps) - 5
            )
            print(f"[VIZ] FPS Limit: {self._settings['fps_limit']}")
        
        def reload_shader() -> None:
            if self._current_shader_path and self._renderer:
                print(f"[VIZ] Reloading shader: {self._current_shader_path}")
                try:
                    # Get existing source nodes
                    old_source_nodes = [n for n in self._dag.root_nodes if isinstance(n, SourceNode)]
                    
                    # Recreate source nodes with same shader path
                    render_specs = self._renderer.pixel_mapper.get_render_specs()
                    glsl_version = self._renderer.get_glsl_version()
                    new_source_nodes = []
                    for i, spec in enumerate(render_specs):
                        node = SourceNode(
                            f"source_{i}",
                            str(self._current_shader_path),
                            spec.width,
                            spec.height,
                            self._renderer.vao,
                            glsl_version=glsl_version
                        )
                        new_source_nodes.append(node)
                    
                    # Swap source nodes, preserving effect chain connections
                    for i in range(max(len(old_source_nodes), len(new_source_nodes))):
                        if i < len(old_source_nodes) and i < len(new_source_nodes):
                            old_source_nodes[i].cleanup()
                            self._dag.swap_source(old_source_nodes[i], new_source_nodes[i])
                        elif i < len(old_source_nodes):
                            old_source_nodes[i].cleanup()
                            self._dag.remove_node(old_source_nodes[i])
                        else:
                            self._dag.add_node(new_source_nodes[i], is_root=True)
                    
                    print(f"[VIZ] Reloaded shader: {self._current_shader_path}")
                except Exception as exc:
                    print(f"[VIZ] Error reloading shader: {exc}")
                    import traceback
                    traceback.print_exc()
        
        def undo_effect() -> None:
            if hasattr(self, "_effect_manager"):
                self._effect_manager.undo_effect(self._dag)
        
        def redo_effect() -> None:
            if hasattr(self, "_effect_manager"):
                self._effect_manager.redo_effect(self._dag)
        
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
    
    def _process_actions(self) -> None:
        """Process input actions (effects, debug toggle, settings, etc.)."""
        if not self._viz_input_manager or not self._renderer:
            return
        
        # Check for exit - close window instead of stopping entire program
        if self._viz_input_manager.is_action_pressed(Action.CANCEL) or self._viz_input_manager.is_action_pressed(Action.BACK):
            print("[VIZ] Close window requested (ESC/CANCEL)")
            if self._viz_window:
                self._viz_window.close()
            self._stop_flag.set()
            return
        
        # Get pressed and held actions
        pressed_actions = self._viz_input_manager.get_pressed_actions()
        held_actions = self._viz_input_manager.get_held_actions()
        
        # Process action handlers (debug toggle, brightness, gamma, fps, reload, undo/redo)
        for action in pressed_actions:
            handler = self._action_handlers.get(action)
            if handler:
                handler()
        
        # Process effects (toggle and momentary) via effect manager
        if hasattr(self, "_effect_manager"):
            try:
                self._effect_manager.process_inputs(pressed_actions, held_actions, self._dag)
            except Exception as exc:
                print(f"[VIZ] Effect manager error: {exc}")
        
        # Note: Parameter source update is handled in _update_uniforms_in_nodes()
        # to avoid duplicate updates (especially for audio mapping source which can be slow)
    
    def _update_fps(self) -> None:
        """Update FPS counter."""
        self._fps_frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._fps_last_time
        if elapsed >= 1.0:
            self._fps_current = self._fps_frame_count / elapsed
            self._fps_frame_count = 0
            self._fps_last_time = current_time
    
    def _deploy_pipeline_internal(self, config: Dict[str, Any]):
        """
        Deploy a pipeline configuration (called from visualization thread).
        
        Args:
            config: Pipeline configuration dict with 'source', 'effects', 'params'
        """
        if not self._renderer:
            print("[VIZ] Cannot deploy pipeline: renderer not initialized")
            return
        
        try:
            # Load shader or video
            source = config.get('source', {})
            shader_path = source.get('shader_path')
            video_path = source.get('video_path')
            pixel_mapper_type = source.get('pixel_mapper', 'surface')
            
            # Preserve effect chain: swap source nodes, keeping connections
            from cube.dag.video_source_node import VideoSourceNode
            
            old_source_nodes = []
            for node in self._dag.nodes:
                if isinstance(node, (SourceNode, VideoSourceNode)):
                    old_source_nodes.append(node)
            
            # Create new source nodes
            render_specs = self._renderer.pixel_mapper.get_render_specs()
            new_source_nodes = []
            
            if video_path:
                print(f"[VIZ] Loading video: {video_path}")
                self._current_shader_path = Path(video_path)
                from cube.dag.frame_loader import VideoFileFrameLoader
                
                video_file_path = Path(video_path)
                if not video_file_path.exists():
                    raise FileNotFoundError(f'Video file not found: {video_path}')
                
                for i, spec in enumerate(render_specs):
                    frame_loader = VideoFileFrameLoader(video_file_path, loop=True)
                    node = VideoSourceNode(
                        f"video_source_{i}",
                        frame_loader,
                        spec.width,
                        spec.height
                    )
                    new_source_nodes.append(node)
            elif shader_path:
                print(f"[VIZ] Loading shader: {shader_path}")
                self._current_shader_path = Path(shader_path)
                
                glsl_version = self._renderer.get_glsl_version()
                for i, spec in enumerate(render_specs):
                    node = SourceNode(
                        f"source_{i}",
                        str(shader_path),
                        spec.width,
                        spec.height,
                        self._renderer.vao,
                        glsl_version=glsl_version
                    )
                    new_source_nodes.append(node)
            
            # Swap source nodes, preserving effect chain connections
            for i in range(max(len(old_source_nodes), len(new_source_nodes))):
                if i < len(old_source_nodes) and i < len(new_source_nodes):
                    # Swap: preserves connections
                    old_source_nodes[i].cleanup()
                    self._dag.swap_source(old_source_nodes[i], new_source_nodes[i])
                elif i < len(old_source_nodes):
                    # More old sources than new: just remove
                    old_source_nodes[i].cleanup()
                    self._dag.remove_node(old_source_nodes[i])
                else:
                    # More new sources than old: just add
                    self._dag.add_node(new_source_nodes[i], is_root=True)
            
            # Update pixel mapper if needed
            if pixel_mapper_type == 'cube':
                camera = SphericalCamera()
                pixel_mapper = CubePixelMapper(
                    face_width=self._panel_width,
                    face_height=self._panel_height,
                    num_panels=self._num_panels
                )
                # Note: Changing pixel mapper requires recreating renderer
                # For now, we'll keep the existing one
            elif pixel_mapper_type == 'surface':
                camera = SphericalCamera()
                pixel_mapper = SurfacePixelMapper(self._width, self._height, camera)
                # Same note as above
            
            # Enable/disable effects
            effects = config.get('effects', [])
            for effect_config in effects:
                action_name = effect_config.get('action')
                enabled = effect_config.get('enabled', False)
                if action_name:
                    from cube.input.actions import Action
                    try:
                        action = Action[action_name]
                        if enabled:
                            self._effect_manager.trigger_effect(action, self._dag)
                        else:
                            self._effect_manager.untoggle_effect(action, self._dag)
                    except (KeyError, AttributeError):
                        print(f"[VIZ] Unknown effect action: {action_name}")
            
            # Set parameters (if needed)
            params = config.get('params')
            if params and hasattr(self, '_parameter_store'):
                # Parameters are managed by ParameterStore via handlers
                # This would need to be implemented if we want to set initial values
                pass
            
            print("[VIZ] Pipeline deployed successfully")
        except Exception as e:
            print(f"[VIZ] Error deploying pipeline: {e}")
            import traceback
            traceback.print_exc()
    
    def deploy_pipeline(self, config: Dict[str, Any]):
        """
        Thread-safe pipeline deployment.
        
        Args:
            config: Pipeline configuration dict
        """
        self._pipeline_queue.put(config)
    
    def save_dag_config(self, file_path: Path):
        """
        Thread-safe DAG configuration save.
        
        Args:
            file_path: Path to save the configuration file
        """
        self._save_config_queue.put(file_path)
    
    def load_dag_config(self, file_path: Path):
        """
        Thread-safe DAG configuration load.
        
        Args:
            file_path: Path to the configuration file to load
        """
        self._load_config_queue.put(file_path)
    
    def _save_dag_config_internal(self, file_path: Path):
        """
        Save DAG configuration (called from visualization thread).
        
        Args:
            file_path: Path to save the configuration file
        """
        if not self._dag or not self._effect_manager:
            print("[VIZ] Cannot save DAG config: DAG or effect manager not initialized")
            return
        
        try:
            from cube.dag.dag_config import DAGConfigEncoder
            config = DAGConfigEncoder.encode(self._dag, self._effect_manager)
            DAGConfigEncoder.save(config, file_path)
            print(f"[VIZ] Saved DAG configuration to {file_path}")
        except Exception as e:
            print(f"[VIZ] Error saving DAG config: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_dag_config_internal(self, file_path: Path):
        """
        Load DAG configuration (called from visualization thread).
        
        Args:
            file_path: Path to the configuration file to load
        """
        if not self._renderer or not self._effect_manager:
            print("[VIZ] Cannot load DAG config: Renderer or effect manager not initialized")
            return
        
        try:
            from cube.dag.dag_config import DAGConfigDecoder
            config = DAGConfigDecoder.load(file_path)
            pipeline_config = DAGConfigDecoder.decode(config, self._renderer, self._effect_manager)
            self._deploy_pipeline_internal(pipeline_config)
            print(f"[VIZ] Loaded DAG configuration from {file_path}")
        except Exception as e:
            print(f"[VIZ] Error loading DAG config: {e}")
            import traceback
            traceback.print_exc()
    
    def get_fps(self) -> float:
        """
        Get current FPS (thread-safe, returns current value).
        
        Returns:
            Current FPS value
        """
        return self._fps_current
    
    def get_debug_state(self) -> Dict[str, Any]:
        """
        Get debug state from parameter store (thread-safe, returns copy).
        
        Returns:
            Dict with params, beat_phase, beat_pulse
        """
        if hasattr(self, '_parameter_store') and self._parameter_store:
            return self._renderer.get_debug_state(self._parameter_store) if self._renderer else {
                'params': [0.0] * 8,
                'beat_phase': 0.0,
                'beat_pulse': 0.0,
            }
        return {
            'params': [0.0] * 8,
            'beat_phase': 0.0,
            'beat_pulse': 0.0,
        }
    
    def get_state(self) -> Dict[str, Any]:
        """
        Query current state (thread-safe, returns copy).
        
        Returns:
            Dict with current shader path, effects, params
        """
        # This would need to be implemented with proper synchronization
        # For now, return basic info
        return {
            'shader_path': getattr(self._renderer, 'shader_path', None) if self._renderer else None,
            'is_running': self._thread is not None and self._thread.is_alive(),
        }
    
    @property
    def effect_manager(self):
        """Get effect manager."""
        return getattr(self, '_effect_manager', None)
    
    def get_camera_source(self):
        """
        Get camera source for debug UI.
        
        Returns a mock object with get_uniforms() and get_camera() methods
        that read from parameter store.
        """
        if not hasattr(self, '_parameter_store') or not self._parameter_store:
            return None
        
        class CameraSourceProxy:
            def __init__(self, param_store, camera_handler):
                self._param_store = param_store
                self._camera_handler = camera_handler
            
            def get_uniforms(self):
                """Get camera uniforms from parameter store."""
                params = self._param_store.get_all_parameters()
                return {
                    'iCameraPos': params.get('iCameraPos', (0.0, 0.0, 0.0)),
                    'iCameraRight': params.get('iCameraRight', (1.0, 0.0, 0.0)),
                    'iCameraUp': params.get('iCameraUp', (0.0, 1.0, 0.0)),
                    'iCameraForward': params.get('iCameraForward', (0.0, 0.0, 1.0)),
                }
            
            def get_camera(self):
                """Get the camera object from camera handler."""
                if self._camera_handler:
                    return getattr(self._camera_handler, 'camera', None)
                return None
        
        return CameraSourceProxy(self._parameter_store, getattr(self, '_camera_handler', None))
    
    def get_mouse_source(self):
        """
        Get mouse source for debug UI.
        
        Returns a mock object with get_uniforms() method that reads from parameter store.
        """
        if not hasattr(self, '_parameter_store') or not self._parameter_store:
            return None
        
        class MouseSourceProxy:
            def __init__(self, param_store):
                self._param_store = param_store
            
            def get_uniforms(self):
                """Get mouse uniforms from parameter store."""
                params = self._param_store.get_all_parameters()
                return {
                    'iMouse': params.get('iMouse', (0.0, 0.0, 0.0, 0.0)),
                }
        
        return MouseSourceProxy(self._parameter_store)
    
    def stop(self, timeout: float = 5.0):
        """
        Graceful shutdown.
        
        Args:
            timeout: Maximum time to wait for thread to stop (seconds)
        """
        if self._thread is None:
            return
        
        print("[MAIN] Stopping visualization thread...")
        self._stop_flag.set()
        self._thread.join(timeout=timeout)
        
        if self._thread.is_alive():
            print(f"[MAIN] Warning: Visualization thread did not stop within {timeout}s")
        else:
            print("[MAIN] Visualization thread stopped")

