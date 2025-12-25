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
from cube.render.pixel_mappers import PixelMapper, SurfacePixelMapper, CubePixelMapper
from cube.shader import SphericalCamera
from cube.input.input_manager import InputManager
from cube.input.actions import Action, InputContext
from cube.input.midi_source import MIDIInputSource
from cube.ui.debug_renderer import DebugRenderer


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
        self._debug_renderer = DebugRenderer()  # Reusable debug renderer
    
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
            
            # Create renderer (uses OpenGL context from pyglet window)
            print("[VIZ] Creating DAG renderer...")
            uniform_sources = []
            if self._midi_uniform_source:
                uniform_sources.append(self._midi_uniform_source)
            
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
                input_manager=self._viz_input_manager,
                settings=self._settings,
                uniform_sources=uniform_sources,
                audio_mapping_source=audio_mapping_source,
                make_context_current=make_context_current,
            )
            print("[VIZ] DAG renderer created")
            
            # Create debug layer (same size as render framebuffer)
            self._debug_layer = np.zeros((self._height, self._width, 3), dtype=np.uint8)
            print("[VIZ] Debug layer created")
            
            # Register action handlers
            self._register_action_handlers()
            
            # Main render loop
            print("[VIZ] Starting render loop...")
            while not self._stop_flag.is_set():
                loop_start = time.time()
                
                # Get current FPS limit (may be updated by action handlers)
                target_fps = self._settings.get('fps_limit', 60)
                frame_time = 1.0 / target_fps
                
                # Make context current (required before any OpenGL calls)
                self._viz_window.backend.window.switch_to()
                
                # Note: Event polling is handled on main thread for macOS compatibility
                # (dispatch_events() must be called from main thread on macOS)
                # We just render here
                
                # Update visualization input (keyboard + MIDI)
                # Keyboard state is updated from main thread's event polling
                # Only poll and process input if visualization window is focused
                if self._viz_window and self._viz_window.is_focused():
                    self._viz_input_manager.poll()
                    
                    # Process actions (effects, debug toggle, settings, etc.)
                    # Only process when window is focused
                    self._process_actions()
                # else: Window not focused, skip input processing
                
                # Check pipeline deployment queue
                try:
                    config = self._pipeline_queue.get_nowait()
                    print("config: ", config)
                    self._deploy_pipeline_internal(config)
                except queue.Empty:
                    pass
                
                # Update renderer from input
                # (Camera, params, effects are handled by DAGRenderer internally)
                
                # Render frame (only if shader is loaded)
                if self._renderer and hasattr(self._renderer, 'current_shader_program') and self._renderer.current_shader_program:
                    # Ensure context is current before rendering
                    self._renderer.make_context_current()
                    
                    # Render to framebuffer (uses FBOs internally)
                    framebuffer = self._renderer.render()
                    
                    # Update FPS counter (always, for debug layer)
                    self._update_fps()
                    
                    # Render debug layer (FPS, params, beat waveforms) if enabled
                    # Skip entirely if debug UI is disabled to avoid overhead
                    debug_enabled = self._settings.get('viz_debug_ui', False)
                    if debug_enabled:
                        # Ensure debug layer matches framebuffer size
                        fb_height, fb_width = framebuffer.shape[:2]
                        if self._debug_layer is None or self._debug_layer.shape[:2] != (fb_height, fb_width):
                            self._debug_layer = np.zeros((fb_height, fb_width, 3), dtype=np.uint8)
                        
                        # Render debug layer using utility
                        self._debug_renderer.render(
                            debug_layer=self._debug_layer,
                            settings=self._settings,
                            fps=self._fps_current,
                            renderer=self._renderer,
                            input_manager=self._viz_input_manager,
                            context='viz',
                        )
                        # Composite debug layer on top of main framebuffer
                        mask = np.any(self._debug_layer != 0, axis=2, keepdims=True)
                        framebuffer = np.where(mask, self._debug_layer, framebuffer)
                    
                    # Send framebuffer to controller (non-blocking, drop if queue full)
                    if self._framebuffer_queue is not None:
                        try:
                            # Put a copy of the framebuffer (non-blocking)
                            # If queue is full, drop the frame (controller will get next one)
                            self._framebuffer_queue.put_nowait(framebuffer.copy())
                        except queue.Full:
                            pass  # Drop frame if queue is full
                    
                    # Display to pyglet window
                    self._viz_window.display(framebuffer)
                # else: No shader loaded yet, skip rendering (will render once pipeline is deployed)
                
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
                    self._renderer.load_shader(str(self._current_shader_path))
                except Exception as exc:
                    print(f"[VIZ] Error reloading shader: {exc}")
        
        def undo_effect() -> None:
            if self._renderer and hasattr(self._renderer, "effect_manager"):
                self._renderer.effect_manager.undo_effect()
        
        def redo_effect() -> None:
            if self._renderer and hasattr(self._renderer, "effect_manager"):
                self._renderer.effect_manager.redo_effect()
        
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
        
        # Check for exit
        if self._viz_input_manager.is_action_pressed(Action.CANCEL) or self._viz_input_manager.is_action_pressed(Action.BACK):
            print("[VIZ] Exit requested (ESC/CANCEL)")
            if self._stop_callback:
                self._stop_callback()
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
        if hasattr(self._renderer, "effect_manager"):
            try:
                self._renderer.effect_manager.process_inputs(pressed_actions, held_actions)
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
            # Load shader
            source = config.get('source', {})
            shader_path = source.get('shader_path')
            pixel_mapper_type = source.get('pixel_mapper', 'surface')
            
            if shader_path:
                print(f"[VIZ] Loading shader: {shader_path}")
                self._current_shader_path = Path(shader_path)
                self._renderer.load_shader(str(shader_path))
            
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
                            self._renderer.effect_manager.trigger_effect(action)
                        else:
                            self._renderer.effect_manager.untoggle_effect(action)
                    except (KeyError, AttributeError):
                        print(f"[VIZ] Unknown effect action: {action_name}")
            
            # Set parameters (if needed)
            params = config.get('params')
            if params and hasattr(self._renderer, 'param_source'):
                # Parameters are managed by ParameterUniformSource via input_manager
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

