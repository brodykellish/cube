"""
Refactored LED Cube Controller - Thread Coordination Only.

The controller's primary purpose is to coordinate between threads:
- Menu thread (main thread)
- Visualization thread (separate thread)

It handles:
- Pipeline deployment (cross-thread communication)
- Thread lifecycle management
- Window creation on main thread (macOS requirement)
"""
import time
import queue
from pathlib import Path
from typing import Optional
import numpy as np

from cube.display.menu_window import MenuWindow
from cube.display.visualization_window import VisualizationWindow
from cube.render.visualization_runner import VisualizationRunner
from cube.ui.dev_menu import DevMenuUI
from cube.midi.midi_manager import MIDIManager
from cube.utils.app_setup import setup_debug_logging, restore_stdout, find_project_root
from cube.menu.actions import (
    MenuAction,
    QuitAction,
    LaunchVisualizationAction,
    SaveDAGConfigAction,
    LoadDAGConfigAction,
)


class CubeController:
    """
    Main controller - coordinates between menu and visualization threads.
    
    Primary responsibility: Cross-thread coordination and pipeline deployment.
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
        # Set up debug logging FIRST (before any threads)
        self.log_lines, self.log_lock, self.stdout_capture, self.original_stdout = setup_debug_logging()

        self.window_width = width
        self.window_height = height
        self.fps = fps
        self.frame_time = 1.0 / fps
        self.num_panels = num_panels
        self.scale = scale

        # Create MenuWindow
        self.menu_window = MenuWindow(width, height, scale=scale, **kwargs)
        self.width = self.menu_window.backend.width
        self.height = self.menu_window.backend.height
        
        # Settings (shared between menu and visualization)
        self.settings = {
            "menu_debug_ui": False,
            "viz_debug_ui": False,
            "debug_axes": False,
            "preview_mode": False,
            "brightness": default_brightness,
            "gamma": default_gamma,
            "fps_limit": fps,
        }

        # Initialize MIDI subsystem
        self.midi_manager = MIDIManager(num_channels=7)

        # MenuWindow owns its own InputManager
        self.menu_input_manager = self.menu_window.input_manager
        self.input_manager = self.menu_input_manager  # Alias for backwards compatibility

        # Visualization window and runner (created lazily)
        self.viz_window: Optional[VisualizationWindow] = None
        self.visualization_runner: Optional[VisualizationRunner] = None
        
        # Queue for receiving rendered framebuffers from visualization thread
        # Max size 1 to always get the latest frame (drops old frames if controller is slow)
        self._framebuffer_queue: Optional[queue.Queue] = queue.Queue(maxsize=1)
        
        # Store latest framebuffer for preview (full resolution, no padding)
        self._latest_framebuffer: Optional[np.ndarray] = None
        
        # Track if visualization window needs to be made visible (after first render)
        self._viz_window_needs_visibility = False

        # Create DevMenuUI
        project_root = find_project_root()
        shaders_dir = project_root / 'shaders'
        self.dev_menu_ui = DevMenuUI(
            width=self.width,
            height=self.height,
            settings=self.settings,
            menu_window=self.menu_window,
            shaders_root=shaders_dir,
            controller=self,  # Pass controller reference for accessing visualization data
        )

        self._cleanup_done = False

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

            # Process menu window events (window handles its own input polling)
            menu_events = self.menu_window.process_events()
            
            # Update forwarding source cache if forwarding is enabled (must be on main thread)
            if (self.dev_menu_ui.input_forwarding_enabled and 
                self.viz_window and 
                hasattr(self.viz_window.input_manager, 'sources')):
                # Find forwarding source and update its cache
                for source in self.viz_window.input_manager.sources:
                    if hasattr(source, 'name') and source.name == 'menu_forwarding':
                        if hasattr(source, 'update_cache'):
                            source.update_cache()
                        break

            # Poll visualization window events (on main thread for macOS compatibility)
            # This must be on main thread because dispatch_events() requires it on macOS
            # Note: VisualizationWindow will handle its own input in its thread
            if self.viz_window:
                self.viz_window.poll()
                
                # Check if close was requested (e.g., by ESC key) and close window on main thread
                if self.viz_window.check_close_request():
                    print("[MAIN] Visualization window close requested, cleaning up...")
                    self._cleanup_visualization()
                # Also check if window was closed externally (e.g., by clicking X button)
                elif not self.viz_window.is_focused():
                    print("[MAIN] Visualization window closed, cleaning up...")
                    self._cleanup_visualization()

            # Receive rendered framebuffer from visualization thread (non-blocking)
            if self._framebuffer_queue is not None:
                try:
                    self._latest_framebuffer = self._framebuffer_queue.get_nowait().copy()
                    
                    # Make window visible after first frame is received (on main thread)
                    if self._viz_window_needs_visibility and self.viz_window:
                        self.viz_window.make_visible()
                        self._viz_window_needs_visibility = False
                    
                    # Visualization is displayed in separate window, no need to update menu layer
                except queue.Empty:
                    pass  # No new frame available

            # Check for quit from menu window
            if (self.menu_input_manager.is_quit_requested() or menu_events.get("quit")):
                running = False
            else:
                # Menu loop (visualization runs in separate thread)
                menu_action = self.dev_menu_ui.update(dt)
                
                # Handle input forwarding toggle
                self._update_input_forwarding()
                
                if menu_action:
                    running = self._handle_action(menu_action)

                # Render menu UI (handles framebuffer composition, corrections, and display)
                self.dev_menu_ui.render()

                frame_time = time.time() - frame_start
                target_fps = self.settings.get("fps_limit", self.fps)
                if target_fps and target_fps > 0:
                    sleep_time = 1.0 / target_fps - frame_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        print("Shutdown complete")
        self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        if self._cleanup_done:
            return
        self._cleanup_done = True

        # Cleanup MIDI
        self.midi_manager.cleanup()

        # Stop visualization thread if it exists
        if self.visualization_runner is not None:
            self.visualization_runner.stop(timeout=5.0)

        # Cleanup windows
        if self.viz_window is not None:
            try:
                self.viz_window.cleanup()
            except Exception:
                pass
        if self.menu_window is not None:
            self.menu_window.cleanup()
    

    def _handle_action(self, action: MenuAction) -> bool:
        """
        Handle actions that require cross-thread coordination.

        Returns:
            True to continue running, False to quit.
        """
        if isinstance(action, QuitAction):
            return False
        if isinstance(action, LaunchVisualizationAction):
            self._launch_visualization(action)
            return True
        if isinstance(action, SaveDAGConfigAction):
            self._save_dag_config(action)
            return True
        if isinstance(action, LoadDAGConfigAction):
            self._load_dag_config(action)
            return True
        # Other actions (PromptAction, MixerAction, etc.) are handled by DevMenuUI
        return True
    
    def _save_dag_config(self, action: SaveDAGConfigAction):
        """Save current DAG configuration."""
        if not self.visualization_runner:
            print("[CONTROLLER] Cannot save DAG config: No visualization running")
            return
        
        from pathlib import Path
        from cube.utils.app_setup import find_project_root
        
        project_root = find_project_root()
        configs_dir = project_root / 'dag_configs'
        configs_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure filename has .yaml extension
        filename = action.filename
        if not filename.endswith(('.yaml', '.yml')):
            filename += '.yaml'
        
        config_path = configs_dir / filename
        self.visualization_runner.save_dag_config(config_path)
        print(f"[CONTROLLER] Saving DAG config to {config_path}")
    
    def _load_dag_config(self, action: LoadDAGConfigAction):
        """Load a saved DAG configuration."""
        if not self.visualization_runner:
            print("[CONTROLLER] Cannot load DAG config: No visualization running")
            # If no visualization is running, we need to start one first
            # For now, just print an error - could launch a default visualization
            return
        
        self.visualization_runner.load_dag_config(action.config_path)
        print(f"[CONTROLLER] Loading DAG config from {action.config_path}")

    def _launch_visualization(self, action: LaunchVisualizationAction):
        """Launch a visualization based on the action configuration."""
        print(f"\n{'============================================================'}")
        print("Launching visualization")
        print(f"Pixel mapper: {action.pixel_mapper}")
        if action.video_path:
            print(f"Video: {action.video_path}")
        elif action.shader_path:
            print(f"Shader: {action.shader_path}")
        print(f"{'============================================================'}")

        try:
            # Create visualization window and runner if they don't exist
            if self.viz_window is None or self.visualization_runner is None:
                print("[MAIN] Creating visualization window and runner...")
                # Create VisualizationWindow on MAIN THREAD (macOS requirement)
                # CRITICAL: Must be created on main thread, not in visualization thread
                self.viz_window = VisualizationWindow(
                    width=self.window_width,
                    height=self.window_height,
                    scale=self.scale,
                    title="Cube Visualization",
                )

                # Create VisualizationRunner (pass window created on main thread)
                self.visualization_runner = VisualizationRunner(
                    width=self.window_width,
                    height=self.window_height,
                    num_panels=self.num_panels,
                    midi_state=self.midi_manager.midi_state,
                    midi_uniform_source=self.midi_manager.midi_uniform_source,
                    settings=self.settings,
                    viz_window=self.viz_window,
                    # Callback to signal stop from viz thread
                    stop_callback=self._stop_visualization,
                    # Queue to receive rendered framebuffers
                    framebuffer_queue=self._framebuffer_queue,
                )

                # Start visualization thread (stdout already redirected, window already created)
                self.visualization_runner.start()
                
                # Track that we need to make window visible after first render
                # This will be done in the main loop after visualization starts rendering
                self._viz_window_needs_visibility = True

            # Deploy pipeline via VisualizationRunner
            source_config = {
                'pixel_mapper': action.pixel_mapper
            }
            if action.video_path:
                source_config['video_path'] = str(action.video_path)
            elif action.shader_path:
                source_config['shader_path'] = str(action.shader_path)
            
            pipeline_config = {
                'source': source_config,
                'effects': [],  # No effects initially
                'params': None  # Use defaults
            }

            # Deploy pipeline (cross-thread communication)
            self.visualization_runner.deploy_pipeline(pipeline_config)

            print(
                "Visualization started. Press ESC in visualization window to return to menu.")
        except Exception as e:
            print(f"Error launching visualization: {e}")
            import traceback
            traceback.print_exc()
            return

    def _cleanup_visualization(self):
        """Clean up visualization thread and window (called from main thread)."""
        print("[MAIN] Cleaning up visualization...")

        # Stop visualization thread (only if it's still running)
        if self.visualization_runner is not None:
            # Check if thread is still alive before trying to stop it
            if self.visualization_runner._thread is not None and self.visualization_runner._thread.is_alive():
                print("[MAIN] Stopping visualization thread...")
                # Set stop flag - thread will exit on its own
                self.visualization_runner._stop_flag.set()
                # Wait for thread to finish (with timeout)
                self.visualization_runner._thread.join(timeout=2.0)
                if self.visualization_runner._thread.is_alive():
                    print("[MAIN] Warning: Visualization thread did not stop within timeout")
            self.visualization_runner = None

        # Cleanup visualization window
        if self.viz_window is not None:
            print("[MAIN] Cleaning up visualization window...")
            try:
                self.viz_window.cleanup()
            except Exception as e:
                print(f"[MAIN] Error cleaning up viz window: {e}")
            self.viz_window = None

        # Return to main menu
        print("Returning to menu...")
        self.dev_menu_ui.navigator.navigate_to("main")

        # Disable input forwarding when visualization stops
        self.dev_menu_ui.input_forwarding_enabled = False
        self._update_input_forwarding()

        print("[MAIN] Visualization cleaned up")
    
    def _stop_visualization(self):
        """Stop visualization thread and cleanup (deprecated - use _cleanup_visualization from main thread)."""
        # This method should not be called from visualization thread anymore
        # It's kept for backwards compatibility but should not be used
        print("[MAIN] Warning: _stop_visualization called (should use _cleanup_visualization from main thread)")
        self._cleanup_visualization()
    
    def _update_input_forwarding(self):
        """Update input forwarding state based on DevMenuUI toggle."""
        if not self.visualization_runner or not self.viz_window:
            return
        
        forwarding_enabled = self.dev_menu_ui.input_forwarding_enabled
        viz_input_manager = self.viz_window.input_manager
        
        # Check if forwarding source is already registered
        forwarding_source = None
        for source in viz_input_manager.sources:
            if hasattr(source, 'name') and source.name == 'menu_forwarding':
                forwarding_source = source
                break
        
        if forwarding_enabled and forwarding_source is None:
            # Enable forwarding: register forwarding source
            from cube.input.forwarding_source import ForwardingInputSource
            # Filter out 't' key (toggle key), but allow numeric keys (1-8) and shift
            # Numeric keys are needed for effect toggles, and shift is needed for shift+1-8
            forwarding_source = ForwardingInputSource(
                self.menu_input_manager,
                midi_state=self.midi_manager.midi_state if self.midi_manager else None,
                filter_keys={'key:t'},  # Only filter out 't' key (toggle forwarding)
                priority=50
            )
            viz_input_manager.register_source(forwarding_source)
            # Set flag in visualization runner to poll even when not focused
            if hasattr(self.visualization_runner, '_input_forwarding_enabled'):
                self.visualization_runner._input_forwarding_enabled = True
            print("[CONTROLLER] Input forwarding enabled")
        elif not forwarding_enabled and forwarding_source is not None:
            # Disable forwarding: unregister forwarding source
            viz_input_manager.sources.remove(forwarding_source)
            forwarding_source.cleanup()
            # Clear flag in visualization runner
            if hasattr(self.visualization_runner, '_input_forwarding_enabled'):
                self.visualization_runner._input_forwarding_enabled = False
            print("[CONTROLLER] Input forwarding disabled")

