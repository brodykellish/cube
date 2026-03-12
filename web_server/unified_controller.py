"""
Unified Controller for LED Cube Visualization and WebSocket Communication.

This controller orchestrates:
1. Single OpenGL visualization process
2. Automatic video streaming when visualization is active
3. Bidirectional WebSocket (video out, controls in)
"""

import threading
import queue
import time
from pathlib import Path
from typing import Optional, Dict, Any

from visualization_manager import VisualizationManager
from streaming_worker import StreamingWorker


class UnifiedController:
    """
    Unified controller that manages visualization and streaming lifecycle.

    Architecture:
    - One OpenGL process (VisualizationManager)
    - Auto-streaming when shader loads
    - Bidirectional WebSocket for video + controls
    """

    def __init__(self, socketio, **viz_config):
        """
        Initialize unified controller.

        Args:
            socketio: SocketIO instance for WebSocket communication
            **viz_config: Configuration for VisualizationManager
        """
        self.socketio = socketio
        self.viz_config = viz_config

        # Visualization manager
        self.viz_manager: Optional[VisualizationManager] = None

        # Streaming worker (always running when viz is active)
        self.streaming_worker: Optional[StreamingWorker] = None

        # State
        self._initialized = False
        self._current_shader = None
        self._current_config = None

        print("[UnifiedController] Created")

    def initialize(self):
        """
        Initialize visualization (must be called from main thread for OpenGL).
        """
        if self._initialized:
            return

        print("[UnifiedController] Initializing visualization...")

        # Create visualization manager
        self.viz_manager = VisualizationManager(**self.viz_config)
        self.viz_manager.initialize()

        self._initialized = True
        print("[UnifiedController] Initialization complete")

    def start(self):
        """Start visualization and streaming."""
        if not self._initialized:
            raise RuntimeError("Must call initialize() first")

        # Start visualization
        print("[UnifiedController] Starting visualization...")
        self.viz_manager.start()

        # Start streaming worker (always active)
        print("[UnifiedController] Starting streaming worker...")
        self.streaming_worker = StreamingWorker(
            framebuffer_queue=self.viz_manager.framebuffer_queue,
            socketio=self.socketio,
            target_fps=60,
            jpeg_quality=95
        )
        self.streaming_worker.start()

        print("[UnifiedController] System running")

    def stop(self):
        """Stop visualization and streaming."""
        if self.streaming_worker:
            self.streaming_worker.stop()
            self.streaming_worker = None

        if self.viz_manager:
            self.viz_manager.stop()

        print("[UnifiedController] System stopped")

    def load_shader(self, shader_path: str) -> bool:
        """
        Load a shader and automatically start streaming.

        Args:
            shader_path: Path to shader (relative to project root)

        Returns:
            bool: True if successful
        """
        if not self.viz_manager or not self.viz_manager.is_running():
            print("[UnifiedController] Visualization not running")
            return False

        try:
            success = self.viz_manager.load_shader(shader_path)
            if success:
                self._current_shader = shader_path
                self._current_config = None

                # Emit event to notify clients
                self.socketio.emit('visualization_loaded', {
                    'type': 'shader',
                    'path': shader_path
                })

                print(f"[UnifiedController] Loaded shader: {shader_path}")
                return True
            return False

        except Exception as e:
            print(f"[UnifiedController] Error loading shader: {e}")
            return False

    def load_config(self, config_path: str) -> bool:
        """
        Load a configuration and automatically start streaming.

        Args:
            config_path: Path to config (relative to dag_configs/)

        Returns:
            bool: True if successful
        """
        if not self.viz_manager or not self.viz_manager.is_running():
            print("[UnifiedController] Visualization not running")
            return False

        try:
            success = self.viz_manager.load_config(config_path)
            if success:
                self._current_shader = None
                self._current_config = config_path

                # Emit event to notify clients
                self.socketio.emit('visualization_loaded', {
                    'type': 'config',
                    'path': config_path
                })

                print(f"[UnifiedController] Loaded config: {config_path}")
                return True
            return False

        except Exception as e:
            print(f"[UnifiedController] Error loading config: {e}")
            return False

    # Control message handlers

    def set_parameter(self, param_id: str, value: float) -> bool:
        """
        Set visualization parameter.

        Args:
            param_id: Parameter ID (e.g., 'iParam0')
            value: Value (0.0-1.0)

        Returns:
            bool: True if successful
        """
        if not self.viz_manager:
            return False

        try:
            self.viz_manager.set_parameter(param_id, value, source='web')
            return True
        except Exception as e:
            print(f"[UnifiedController] Error setting parameter: {e}")
            return False

    def toggle_effect(self, effect_action: str) -> bool:
        """
        Toggle an effect on/off.

        Args:
            effect_action: Effect action name

        Returns:
            bool: True if successful
        """
        if not self.viz_manager:
            return False

        try:
            self.viz_manager.toggle_effect(effect_action)

            # Emit current active effects
            active = self.viz_manager.get_active_effects()
            self.socketio.emit('effects_changed', {'active_effects': active})

            return True
        except Exception as e:
            print(f"[UnifiedController] Error toggling effect: {e}")
            return False

    def emulate_key_press(self, key: str) -> bool:
        """
        Emulate a keyboard key press.

        Args:
            key: Key to press (e.g., 'm', 'n', '1', '2')

        Returns:
            bool: True if successful
        """
        # TODO: Implement keyboard emulation through input manager
        print(f"[UnifiedController] Key press emulation not yet implemented: {key}")
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        status = {
            'initialized': self._initialized,
            'running': self.viz_manager.is_running() if self.viz_manager else False,
            'current_shader': self._current_shader,
            'current_config': self._current_config,
            'streaming': self.streaming_worker.is_running() if self.streaming_worker else False,
        }

        if self.viz_manager:
            status['visualization'] = self.viz_manager.get_stats()

        if self.streaming_worker:
            status['streaming'] = self.streaming_worker.get_stats()

        return status
