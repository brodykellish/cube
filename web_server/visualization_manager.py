"""
Visualization Manager for Web Server.

Manages the LED cube visualization as a background process,
providing a single-process solution for web-based control.
"""

import threading
import queue
import time
from pathlib import Path
from typing import Optional, Dict, Any

from cube.display.visualization_window import VisualizationWindow
from cube.render.visualization_runner import VisualizationRunner
from cube.midi import MIDIState, USBMIDIDriver, load_midi_config
from cube.dag.dag import DAG
from cube.render.effect_manager import EffectManager
from cube.render.effect_config_loader import load_effect_config
from cube.render.parameter_store import ParameterStore


class VisualizationManager:
    """
    Manages visualization in background thread for web server.

    Provides single-process solution where web server controls visualization.

    Features:
    - Background visualization rendering
    - Framebuffer queue for video streaming
    - API for controlling effects and parameters
    - Automatic initialization on startup
    """

    def __init__(
        self,
        width: int = 384,
        height: int = 64,
        num_panels: int = 6,
        fps: int = 60,
        headless: bool = False
    ):
        """
        Initialize visualization manager.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            num_panels: Number of cube panels
            fps: Target FPS
            headless: If True, create hidden window
        """
        self.width = width
        self.height = height
        self.num_panels = num_panels
        self.fps = fps
        self.headless = headless

        # Framebuffer queue for streaming
        self.framebuffer_queue = queue.Queue(maxsize=3)

        # Visualization components (created in main thread)
        self.viz_window: Optional[VisualizationWindow] = None
        self.viz_runner: Optional[VisualizationRunner] = None

        # MIDI components
        self.midi_state: Optional[MIDIState] = None
        self.usb_midi: Optional[USBMIDIDriver] = None

        # DAG and effects (accessed via runner)
        self.dag: Optional[DAG] = None
        self.effect_manager: Optional[EffectManager] = None
        self.parameter_store: Optional[ParameterStore] = None

        # State
        self._initialized = False
        self._running = False

    def initialize(self):
        """
        Initialize visualization components.

        MUST be called from main thread (macOS OpenGL requirement).
        """
        if self._initialized:
            return

        print("[VizManager] Initializing visualization...")

        # Initialize MIDI
        self.midi_state = MIDIState(num_channels=8)
        midi_config = load_midi_config()
        self.usb_midi = USBMIDIDriver(self.midi_state, midi_config, tap_note=43)

        if self.usb_midi.is_connected():
            print(f'[VizManager] USB MIDI connected: {self.usb_midi.connected_device}')

        # Create visualization window (must be on main thread for macOS)
        print(f"[VizManager] Creating window {self.width}x{self.height}...")
        self.viz_window = VisualizationWindow(
            self.width,
            self.height,
            scale=1,
            backend='pyglet'  # Use pyglet for compatibility
        )

        # Make window small and hidden if headless
        if self.headless and hasattr(self.viz_window.backend, 'window'):
            self.viz_window.backend.window.set_visible(False)
            print("[VizManager] Running in headless mode (window hidden)")

        # Settings for renderer
        settings = {
            "menu_debug_ui": False,
            "viz_debug_ui": False,
            "debug_axes": False,
            "preview_mode": False,
            "brightness": 80.0,
            "gamma": 1.0,
            "fps_limit": self.fps,
        }

        # Create visualization runner
        self.viz_runner = VisualizationRunner(
            width=self.width,
            height=self.height,
            num_panels=self.num_panels,
            midi_state=self.midi_state,
            usb_midi=self.usb_midi,
            settings=settings,
            viz_window=self.viz_window,
            framebuffer_queue=self.framebuffer_queue
        )

        # DAG and effects will be created by the visualization runner
        # We don't create them here because EffectManager needs the renderer
        self.dag = None
        self.effect_manager = None
        self.parameter_store = None

        self._initialized = True
        print("[VizManager] Initialization complete")

    def start(self):
        """Start visualization rendering in background thread."""
        if not self._initialized:
            raise RuntimeError("Must call initialize() before start()")

        if self._running:
            return

        print("[VizManager] Starting visualization thread...")
        self.viz_runner.start()
        self._running = True
        print("[VizManager] Visualization running")

    def stop(self):
        """Stop visualization rendering."""
        if not self._running:
            return

        print("[VizManager] Stopping visualization...")
        if self.viz_runner:
            self.viz_runner.request_stop()

        self._running = False
        print("[VizManager] Visualization stopped")

    def deploy_pipeline(self, dag: DAG, effect_manager: EffectManager):
        """
        Deploy new visualization pipeline.

        Args:
            dag: DAG to deploy
            effect_manager: EffectManager with active effects
        """
        if not self._running:
            raise RuntimeError("Visualization not running")

        self.dag = dag
        self.effect_manager = effect_manager

        self.viz_runner.deploy_pipeline(dag, effect_manager)
        print("[VizManager] Pipeline deployed")

    def set_parameter(self, param_id: str, value: float, source: str = 'web'):
        """
        Set visualization parameter.

        Args:
            param_id: Parameter ID (e.g., 'iParam0')
            value: Parameter value (0.0-1.0)
            source: Source of parameter change
        """
        if not self.parameter_store:
            print(f"[VizManager] Warning: Parameter store not initialized")
            return

        # Set parameter in store
        param = self.parameter_store.get_parameter(param_id)
        if param:
            param.set_value(value)
            print(f"[VizManager] Set {param_id} = {value:.2f} (source: {source})")
        else:
            print(f"[VizManager] Warning: Unknown parameter {param_id}")

    def enable_effect(self, action: str):
        """
        Enable an effect.

        Args:
            action: Effect action name
        """
        if not self.effect_manager:
            print("[VizManager] Warning: Effect manager not initialized")
            return

        if action in self.effect_manager.effects:
            self.effect_manager.enable_effect(action)
            print(f"[VizManager] Enabled effect: {action}")

            # Redeploy pipeline to apply effect
            if self.dag:
                self.deploy_pipeline(self.dag, self.effect_manager)
        else:
            print(f"[VizManager] Warning: Unknown effect {action}")

    def disable_effect(self, action: str):
        """
        Disable an effect.

        Args:
            action: Effect action name
        """
        if not self.effect_manager:
            print("[VizManager] Warning: Effect manager not initialized")
            return

        if action in self.effect_manager.effects:
            self.effect_manager.disable_effect(action)
            print(f"[VizManager] Disabled effect: {action}")

            # Redeploy pipeline to apply effect
            if self.dag:
                self.deploy_pipeline(self.dag, self.effect_manager)
        else:
            print(f"[VizManager] Warning: Unknown effect {action}")

    def toggle_effect(self, action: str):
        """
        Toggle an effect on/off.

        Args:
            action: Effect action name
        """
        if not self.effect_manager:
            return

        if action in self.effect_manager.active_effects:
            self.disable_effect(action)
        else:
            self.enable_effect(action)

    def get_active_effects(self):
        """Get list of currently active effects."""
        if not self.effect_manager:
            return []
        return list(self.effect_manager.active_effects)

    def is_running(self):
        """Check if visualization is running."""
        return self._running

    def get_stats(self) -> Dict[str, Any]:
        """Get visualization statistics."""
        return {
            'initialized': self._initialized,
            'running': self._running,
            'width': self.width,
            'height': self.height,
            'num_panels': self.num_panels,
            'fps': self.fps,
            'headless': self.headless,
            'framebuffer_queue_size': self.framebuffer_queue.qsize() if self.framebuffer_queue else 0,
            'active_effects': self.get_active_effects() if self.effect_manager else [],
            'midi_connected': self.usb_midi.is_connected() if self.usb_midi else False
        }
