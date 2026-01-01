#!/usr/bin/env python3
"""
Pi Cube Control - Single-process entrypoint for Raspberry Pi.

Uses piomatter backend with three-layer compositing:
- Layer 0: Menu
- Layer 1: Visualization
- Layer 2: Debug UI

All rendering happens in a single process with SSHKeyboard and MIDI input.

NOTE: This script uses pygame backend for development/testing.
For Raspberry Pi deployment, it will use piomatter backend.
"""

import os
import sys

# Configure PyOpenGL platform for Linux
if sys.platform == 'linux':
    os.environ['PYOPENGL_PLATFORM'] = 'egl'

import argparse
import time
import atexit
from pathlib import Path
from typing import Optional
import numpy as np
import platform

from cube.display.display import Display
from cube.input.input_manager import InputManager
from cube.input.keyboard_source import KeyboardInputSource
from cube.input.midi_source import MIDIInputSource
from cube.input.actions import InputContext, Action
from cube.midi import MIDIState, MIDIKeyboardDriver, USBMIDIDriver, load_midi_config
from cube.ui.dev_menu import DevMenuUI
from cube.ui.debug_ui import DebugUIRenderer, DebugUIData, collect_debug_data
from cube.menu.actions import MenuAction, LaunchVisualizationAction, QuitAction
from cube.render.dag_renderer import DAGRenderer
from cube.render.pixel_mappers import SurfacePixelMapper, CubePixelMapper
from cube.shader import SphericalCamera
from cube.dag.dag import DAG
from cube.dag.source_node import SourceNode
from cube.utils.app_setup import find_project_root


class PiCubeController:
    """
    Single-process controller for Raspberry Pi.
    
    Manages menu, visualization, and debug UI in one process.
    Uses three-layer compositing system.
    """
    
    def __init__(
        self,
        width: int,
        height: int,
        num_panels: int = 6,
        fps: int = 60,
        default_brightness: float = 60.0,
        default_gamma: float = 2.2,
        use_pygame: bool = False,
        **kwargs
    ):
        """Initialize the Pi cube controller."""
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_time = 1.0 / fps
        self.num_panels = num_panels
        
        # Settings
        self.settings = {
            "menu_debug_ui": False,
            "viz_debug_ui": False,
            "debug_axes": False,
            "preview_mode": False,
            "brightness": default_brightness,
            "gamma": default_gamma,
            "fps_limit": fps,
        }
        
        # Determine backend type
        # Use pygame for development (macOS/Windows) or if explicitly requested
        is_dev_platform = platform.system() in ('Darwin', 'Windows')
        use_pygame_backend = use_pygame or is_dev_platform
        
        if use_pygame_backend:
            # Use pygame backend for development/testing
            from cube.display.pygame_backend import PygameBackend
            self.backend = PygameBackend(width, height, **kwargs)
            print("[PI] Using pygame backend (development mode)")
        else:
            # Use piomatter backend for Raspberry Pi
            try:
                import piomatter
                if not piomatter._PIOMATTER_AVAILABLE:
                    raise RuntimeError(
                        'piomatter C extension is not available. '
                        'Make sure you\'re running on a Raspberry Pi 5 and the extension is built correctly.'
                    )
                from cube.display.piomatter_backend import PiomatterBackend
                self.backend = PiomatterBackend(width, height, **kwargs)
                print("[PI] Using piomatter backend (Raspberry Pi)")
            except (ImportError, RuntimeError) as e:
                print(f"[PI] Error: {e}")
                print("[PI] Falling back to pygame backend for development")
                from cube.display.pygame_backend import PygameBackend
                self.backend = PygameBackend(width, height, **kwargs)
        
        # Create Display with 3 layers (menu, visualization, debug)
        self.display = Display(
            width=width,
            height=height,
            num_layers=3,
            backend=self.backend,
            backend_type='auto',  # Let Display detect based on backend
            **kwargs
        )
        
        # Initialize MIDI subsystem
        self.midi_state = MIDIState(num_channels=8)
        self.midi_keyboard_driver = MIDIKeyboardDriver(self.midi_state)
        
        # Initialize USB MIDI
        self.midi_config = load_midi_config()
        self.usb_midi: Optional[USBMIDIDriver] = None
        self.usb_midi = USBMIDIDriver(
            self.midi_state, self.midi_config, tap_note=43)
        if self.usb_midi.is_connected():
            print(f'[PI] USB MIDI controller connected: {self.usb_midi.connected_device}')
        else:
            print('[PI] USB MIDI device not connected')
        
        # Create input manager for menu
        self.menu_input_manager = InputManager()
        self.menu_input_manager.set_context(InputContext.MENU)
        
        # Register keyboard source (from backend)
        if hasattr(self.backend, 'keyboard'):
            self.menu_input_manager.register_source(
                KeyboardInputSource(self.backend.keyboard))
        else:
            # Fallback: create SSH keyboard if backend doesn't provide one
            from cube.input.ssh_keyboard import SSHKeyboard
            ssh_key_hold_duration = kwargs.get('ssh_key_hold_duration', 0.15)
            keyboard = SSHKeyboard(key_hold_duration=ssh_key_hold_duration)
            self.menu_input_manager.register_source(
                KeyboardInputSource(keyboard))
        
        # Register MIDI source
        self.menu_input_manager.register_source(
            MIDIInputSource(self.midi_state))
        
        # Create menu UI (but we'll render to our own layer)
        project_root = find_project_root()
        shaders_dir = project_root / 'shaders'
        
        # Create a mock menu window for DevMenuUI (it needs one, but we'll render to our layer)
        class MockMenuWindow:
            def __init__(self, backend, input_manager, midi_state, midi_keyboard_driver):
                self.backend = backend
                self.input_manager = input_manager
                self.midi_state = midi_state
                self.midi_keyboard_driver = midi_keyboard_driver
            def show_framebuffer(self, framebuffer):
                pass  # We'll handle display ourselves
            def setup_midi(self, midi_state, midi_keyboard_driver):
                # Already set up in __init__, but DevMenuUI might call this
                self.midi_state = midi_state
                self.midi_keyboard_driver = midi_keyboard_driver
            def process_events(self):
                # Return events dict for compatibility
                events = self.backend.handle_events()
                # Process MIDI keyboard input if driver exists
                if self.midi_keyboard_driver:
                    dt = 1.0 / 60.0  # Approximate delta time
                    if events.get('key'):
                        self.midi_keyboard_driver.handle_key(events['key'])
                    held_keys = events.get('keys', [])
                    if held_keys:
                        self.midi_keyboard_driver.update_from_held_keys(held_keys, dt)
                return events
        
        self.mock_menu_window = MockMenuWindow(
            self.backend, 
            self.menu_input_manager,
            self.midi_state,
            self.midi_keyboard_driver
        )
        
        self.dev_menu_ui = DevMenuUI(
            width=self.width,
            height=self.height,
            settings=self.settings,
            menu_window=self.mock_menu_window,
            shaders_root=shaders_dir,
            controller=self,
        )
        
        # Setup MIDI on menu window (DevMenuUI might expect this)
        self.mock_menu_window.setup_midi(self.midi_state, self.midi_keyboard_driver)
        
        # Visualization state
        self.visualization_running = False
        self.visualization_hidden = False  # True when visualization is active and menu is hidden
        self._renderer: Optional[DAGRenderer] = None
        self._dag: Optional[DAG] = None
        self._parameter_store = None
        self._pixel_mapper = None
        self._camera = None
        
        # Input manager for visualization
        self.viz_input_manager = InputManager()
        self.viz_input_manager.set_context(InputContext.VISUALIZATION)
        if hasattr(self.backend, 'keyboard'):
            self.viz_input_manager.register_source(
                KeyboardInputSource(self.backend.keyboard))
        self.viz_input_manager.register_source(
            MIDIInputSource(self.midi_state))
        
        # Debug UI
        self.debug_ui_renderer = DebugUIRenderer()
        self.debug_data = DebugUIData()
        self.debug_visible = False
        
        # FPS tracking
        self._fps_current = 0.0
        self._fps_last_time = time.time()
        self._fps_frame_count = 0
        
        # Cleanup flag
        self._cleanup_done = False
        
        print(f"[PI] Controller initialized: {width}×{height}, {num_panels} panels")
    
    def run(self):
        """Main loop."""
        print("\nStarting Pi cube controller...")
        print("Controls:")
        print("  - Arrow keys to navigate menu")
        print("  - Enter to select / start visualization")
        print("  - Escape to return to menu / stop visualization")
        print("  - 'd' to toggle debug UI")
        
        running = True
        last_frame_time = time.time()
        
        while running:
            frame_start = time.time()
            dt = frame_start - last_frame_time
            last_frame_time = frame_start
            
            # Poll USB MIDI
            if self.usb_midi:
                self.usb_midi.poll()
            
            # Handle events from backend
            events = self.backend.handle_events()
            
            # Check for quit
            if events.get('quit') or self.menu_input_manager.is_quit_requested():
                running = False
                break
            
            # Update input managers
            self.menu_input_manager.poll()
            
            # Process menu window events (for MIDI keyboard driver)
            self.mock_menu_window.process_events()
            
            # Handle escape key - return to menu
            if events.get('key') == 'escape' and self.visualization_running:
                self._stop_visualization()
            
            # Handle debug toggle
            if self.menu_input_manager.is_action_pressed(Action.TOGGLE_DEBUG):
                self.debug_visible = not self.debug_visible
            
            # Update menu (if not hidden)
            if not self.visualization_hidden:
                menu_action = self.dev_menu_ui.update(dt)
                if isinstance(menu_action, QuitAction):
                    running = False
                    break
                elif isinstance(menu_action, LaunchVisualizationAction):
                    self._launch_visualization(menu_action)
                    self.visualization_hidden = True
            elif self.visualization_running:
                # Menu is hidden but visualization is running
                # Handle enter key to hide menu (if it wasn't already hidden)
                if events.get('key') == 'enter' and not self.visualization_hidden:
                    self.visualization_hidden = True
            
            # Update visualization (if running)
            if self.visualization_running:
                self.viz_input_manager.poll()
                self._update_visualization(dt)
            
            # Render all layers
            self._render_all_layers()
            
            # Update FPS
            self._update_fps()
            
            # Frame rate limiting
            frame_time = time.time() - frame_start
            target_fps = self.settings.get("fps_limit", self.fps)
            if target_fps and target_fps > 0:
                sleep_time = 1.0 / target_fps - frame_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        print("Shutdown complete")
        self.cleanup()
    
    def _launch_visualization(self, action: LaunchVisualizationAction):
        """Launch a visualization based on the action."""
        print(f"\n{'='*60}")
        print("Launching visualization")
        print(f"Pixel mapper: {action.pixel_mapper}")
        if action.video_path:
            print(f"Video: {action.video_path}")
        elif action.shader_path:
            print(f"Shader: {action.shader_path}")
        print(f"{'='*60}")
        
        try:
            # Initialize renderer if needed
            if self._renderer is None:
                print("[PI] Initializing visualization renderer...")
                
                # Create camera and pixel mapper
                self._camera = SphericalCamera()
                if action.pixel_mapper == 'cube':
                    self._pixel_mapper = CubePixelMapper(
                        self.width, self.height, self.num_panels, self._camera)
                else:
                    self._pixel_mapper = SurfacePixelMapper(
                        self.width, self.height, self._camera)
                
                # Create parameter store
                from cube.render.parameter_store import (
                    ParameterStore, ParameterHandlerRegistry,
                    TimeHandler, CameraHandler, MouseHandler,
                    SignalParameterHandler, SettingsParameterHandler
                )
                
                # Audio mapping (optional)
                audio_mapping_source = None
                try:
                    from cube.audio.shared_state import AudioStateReader
                    from cube.shader.audio_uniform_mapping_source import AudioUniformMappingSource
                    audio_mapping_source = AudioUniformMappingSource(AudioStateReader())
                except Exception:
                    pass
                
                # Create parameter store
                self._parameter_store = ParameterStore(settings=self.settings)
                
                # Create handlers
                handler_registry = ParameterHandlerRegistry()
                
                # Time handler
                time_handler = TimeHandler(self._parameter_store)
                handler_registry.register(time_handler)
                
                # Camera handler
                camera_handler = CameraHandler(self._parameter_store, self._camera, self.viz_input_manager)
                handler_registry.register(camera_handler)
                
                # Mouse handler
                mouse_handler = MouseHandler(self._parameter_store, self.width, self.height)
                handler_registry.register(mouse_handler)
                
                # Signal handlers for iParam0-7 (keyboard and MIDI)
                from cube.core.signals import KeyboardParamSignal, MIDISignal
                from cube.input.actions import Action, Axis
                
                for i in range(8):
                    param_id = f'iParam{i}'
                    param_axis = getattr(Axis, f'PARAM{i}')
                    inc_action = getattr(Action, f'INC_PARAM{i}')
                    dec_action = getattr(Action, f'DEC_PARAM{i}')
                    
                    # Keyboard signal handler (discrete actions: INC/DEC)
                    keyboard_signal = KeyboardParamSignal(self.viz_input_manager, param_axis, inc_action, dec_action)
                    keyboard_handler = SignalParameterHandler(
                        self._parameter_store,
                        keyboard_signal,
                        param_id,
                        priority=0  # Low priority
                    )
                    handler_registry.register(keyboard_handler)
                    
                    # MIDI signal handler (continuous axes: direct CC values)
                    midi_signal = MIDISignal(self.viz_input_manager, param_axis)
                    midi_handler = SignalParameterHandler(
                        self._parameter_store,
                        midi_signal,
                        param_id,
                        priority=100  # High priority - overrides keyboard
                    )
                    handler_registry.register(midi_handler)
                
                # Audio signal handlers (if available) - simplified for now
                # Audio mapping is complex and can be added later if needed
                
                # Settings handler
                settings_handler = SettingsParameterHandler(self._parameter_store, self.settings)
                handler_registry.register(settings_handler)
                
                # Store handler registry for updates
                self._handler_registry = handler_registry
                
                # Create renderer (it will create its own offscreen context)
                self._renderer = DAGRenderer(
                    pixel_mapper=self._pixel_mapper,
                )
                print("[PI] Visualization renderer initialized")
            
            # Create DAG with source node
            self._dag = DAG()
            
            source_config = {
                'pixel_mapper': action.pixel_mapper
            }
            if action.video_path:
                source_config['video_path'] = str(action.video_path)
            elif action.shader_path:
                source_config['shader_path'] = str(action.shader_path)
            
            source_node = SourceNode.create_from_config(source_config)
            self._dag.add_node(source_node)
            
            self.visualization_running = True
            print("[PI] Visualization started")
            
        except Exception as e:
            print(f"[PI] Error launching visualization: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_visualization(self, dt: float):
        """Update visualization state."""
        if not self._renderer or not self._dag:
            return
        
        # Update parameter handlers (they update the parameter store)
        if hasattr(self, '_handler_registry'):
            self._handler_registry.update_all(dt)
    
    def _stop_visualization(self):
        """Stop visualization and return to menu."""
        print("[PI] Stopping visualization...")
        self.visualization_running = False
        self.visualization_hidden = False
        # Keep renderer and DAG alive for faster restart
        print("[PI] Returned to menu")
    
    def _render_all_layers(self):
        """Render all three layers and composite."""
        # Clear all layers
        menu_layer = self.display.get_layer(0)
        viz_layer = self.display.get_layer(1)
        debug_layer = self.display.get_layer(2)
        
        menu_layer[:, :, :] = 0
        viz_layer[:, :, :] = 0
        debug_layer[:, :, :] = 0
        
        # Render menu (layer 0) - if not hidden
        if not self.visualization_hidden:
            # Get menu framebuffer from DevMenuUI
            # We need to render it ourselves since we're not using MenuWindow
            self.dev_menu_ui.menu_layer[:, :, :] = 0
            self.dev_menu_ui.navigator.render(self.dev_menu_ui.renderer)
            menu_layer[:, :, :] = self.dev_menu_ui.menu_layer[:, :, :]
        
        # Render visualization (layer 1) - if running
        if self.visualization_running and self._renderer and self._dag:
            try:
                # Make context current before rendering
                if not self._renderer.make_context_current():
                    print("[PI] Warning: Failed to make OpenGL context current")
                else:
                    framebuffer = self._renderer.render(self._dag, self._parameter_store)
                    if framebuffer is not None:
                        # Resize if needed
                        if framebuffer.shape[:2] != (self.height, self.width):
                            import cv2
                            framebuffer = cv2.resize(framebuffer, (self.width, self.height))
                        viz_layer[:, :, :] = framebuffer
            except Exception as e:
                print(f"[PI] Error rendering visualization: {e}")
                import traceback
                traceback.print_exc()
        
        # Render debug UI (layer 2) - if visible
        if self.debug_visible:
            # Collect debug data
            try:
                debug_data = collect_debug_data(
                    visualization_runner=None,  # We don't have a runner in single-process mode
                    viz_window=None,
                    preview_framebuffer=viz_layer if self.visualization_running else None,
                    viz_input_manager=self.viz_input_manager if self.visualization_running else None,
                )
                debug_data.visualization_running = self.visualization_running
                debug_data.fps = self._fps_current
                self.debug_data = debug_data
            except Exception as e:
                print(f"[PI] Error collecting debug data: {e}")
            
            # Render debug UI
            debug_height = min(256, self.height // 4)
            debug_width = self.width
            debug_fb = np.zeros((debug_height, debug_width, 3), dtype=np.uint8)
            debug_fb[:, :] = (173, 216, 230)  # Light blue background
            
            # Render debug UI components
            element_width = debug_width // 3
            x_positions = [i * element_width for i in range(3)]
            
            # Effects list
            effects_rendered = self.debug_ui_renderer.render_effects_list_pygame(
                element_width, debug_height, self.debug_data
            )
            debug_fb[:, x_positions[0]:x_positions[0] + element_width] = effects_rendered[:, :element_width]
            
            # Preview
            preview_rendered = self.debug_ui_renderer.render_preview(
                element_width, debug_height, self.debug_data
            )
            debug_fb[:, x_positions[1]:x_positions[1] + element_width] = preview_rendered[:, :element_width]
            
            # Debug info
            debug_info_rendered = self.debug_ui_renderer.render_debug_info(
                element_width, debug_height, self.debug_data
            )
            debug_fb[:, x_positions[2]:x_positions[2] + element_width] = debug_info_rendered[:, :element_width]
            
            # Place debug layer at bottom of screen
            debug_start_y = self.height - debug_height
            debug_layer[debug_start_y:, :] = debug_fb
        
        # Composite and display
        self.display.show(
            brightness=self.settings.get('brightness', 60.0),
            gamma=self.settings.get('gamma', 2.2)
        )
    
    def _update_fps(self):
        """Update FPS counter."""
        self._fps_frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._fps_last_time
        if elapsed >= 1.0:
            self._fps_current = self._fps_frame_count / elapsed
            self._fps_frame_count = 0
            self._fps_last_time = current_time
    
    def cleanup(self):
        """Clean up resources."""
        if self._cleanup_done:
            return
        self._cleanup_done = True
        
        # Cleanup MIDI
        if self.usb_midi:
            self.usb_midi.cleanup()
        
        # Cleanup display
        if self.display:
            self.display.cleanup()
        
        print("[PI] Cleanup complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Pi Cube Control - Single-process entrypoint for Raspberry Pi"
    )
    
    parser.add_argument(
        "--width",
        type=int,
        required=True,
        help="Display width in pixels"
    )
    
    parser.add_argument(
        "--height",
        type=int,
        required=True,
        help="Display height in pixels"
    )
    
    parser.add_argument(
        "--num-panels",
        type=int,
        default=4,
        help="Number of cube panels/faces (default: 4)"
    )
    
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="Target frames per second (default: 60)"
    )
    
    parser.add_argument(
        "--brightness",
        type=float,
        default=80.0,
        help="Default brightness percentage (1-90, default: 80)"
    )
    
    parser.add_argument(
        "--gamma",
        type=float,
        default=1.0,
        help="Default gamma correction value (0.5-3.0, default: 1.0)"
    )
    
    parser.add_argument(
        "--pinout",
        type=str,
        default="AdafruitMatrixBonnet",
        help="Hardware pinout configuration (default: AdafruitMatrixBonnet)"
    )
    
    parser.add_argument(
        "--num-planes",
        type=int,
        default=10,
        help="Color depth in bit-planes (4-11, default: 10)"
    )
    
    parser.add_argument(
        "--num-address-lines",
        type=int,
        default=5,
        help="Address lines: 4 for 32-pixel tall, 5 for 64-pixel (default: 5)"
    )
    
    parser.add_argument(
        "--ssh-key-hold",
        type=float,
        default=0.15,
        dest="ssh_key_hold_duration",
        help="SSH keyboard hold duration in seconds (0.05-0.5, default: 0.15)"
    )
    
    parser.add_argument(
        "--use-pygame",
        action="store_true",
        help="Force pygame backend (for development/testing)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.num_panels < 1 or args.num_panels > 6:
        parser.error("--num-panels must be between 1 and 6")
    if args.brightness < 1 or args.brightness > 90:
        parser.error("--brightness must be between 1 and 90")
    if args.gamma < 0.5 or args.gamma > 3.0:
        parser.error("--gamma must be between 0.5 and 3.0")
    if args.ssh_key_hold_duration < 0.05 or args.ssh_key_hold_duration > 0.5:
        parser.error("--ssh-key-hold must be between 0.05 and 0.5")
    
    # Print startup banner
    print("=" * 60)
    print("PI CUBE CONTROL")
    print("=" * 60)
    print(f"Display Size: {args.width}×{args.height}")
    print(f"Panels: {args.num_panels}")
    print(f"Target FPS: {args.fps}")
    print(f"Brightness: {args.brightness}%")
    print(f"Gamma: {args.gamma}")
    print("=" * 60)
    print()
    
    # Create and run controller
    controller = None
    try:
        controller = PiCubeController(
            width=args.width,
            height=args.height,
            num_panels=args.num_panels,
            fps=args.fps,
            default_brightness=args.brightness,
            default_gamma=args.gamma,
            pinout=args.pinout,
            num_planes=args.num_planes,
            num_address_lines=args.num_address_lines,
            ssh_key_hold_duration=args.ssh_key_hold_duration,
            use_pygame=args.use_pygame,
        )
        
        # Register cleanup
        atexit.register(controller.cleanup)
        
        controller.run()
        
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if controller:
            controller.cleanup()


if __name__ == "__main__":
    main()

