"""
Core Visualization API

Provides a thread-safe, high-performance interface for managing visualizations,
parameters, effects, and DAG pipelines.

Design Principles:
- Minimal API surface
- Thread-safe operations
- High-frequency parameter updates (120+ FPS)
- Clean separation of concerns
"""
import threading
import queue
import time
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from cube.display.visualization_window import VisualizationWindow
from cube.render.visualization_runner import VisualizationRunner
from cube.midi.midi_state import MIDIState
from cube.midi.usb_driver import USBMIDIDriver
from cube.core.parameter import ParameterType


class VisualizationStatus(Enum):
    """Visualization lifecycle status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class VisualizationSettings:
    """Visualization display settings."""
    brightness: float = 60.0
    gamma: float = 2.2
    fps_limit: int = 60
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VisualizationSettings':
        return cls(**{k: v for k, v in data.items() if k in ['brightness', 'gamma', 'fps_limit']})




class VisualizationAPI:
    """
    Core API for visualization management.
    
    Thread-safe interface for:
    - Starting/stopping visualizations
    - Deploying and updating DAG pipelines
    - High-frequency parameter updates (120+ FPS)
    - Effect management
    - Settings management
    
    All operations are thread-safe and designed for use from web API handlers.
    """
    
    def __init__(
        self,
        width: int = 64,
        height: int = 64,
        num_panels: int = 6,
        scale: int = 1,
        midi_state: Optional[MIDIState] = None,
        usb_midi: Optional[USBMIDIDriver] = None,
        initial_settings: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the visualization API.
        
        Args:
            width: Window width in pixels
            height: Window height in pixels
            num_panels: Number of cube panels
            scale: Content scale factor
            midi_state: Optional MIDI state for MIDI input
            usb_midi: Optional USB MIDI driver
            initial_settings: Initial settings dictionary
        """
        self._width = width
        self._height = height
        self._num_panels = num_panels
        self._scale = scale
        self._midi_state = midi_state
        self._usb_midi = usb_midi
        
        # Thread-safe state
        self._lock = threading.RLock()
        self._status = VisualizationStatus.STOPPED
        self._error_message: Optional[str] = None
        
        # Visualization components (created on main thread)
        self._viz_window: Optional[VisualizationWindow] = None
        self._viz_runner: Optional[VisualizationRunner] = None
        
        # Settings
        default_settings = {
            "menu_debug_ui": False,
            "viz_debug_ui": False,
            "debug_axes": False,
            "preview_mode": False,
            "brightness": 60.0,
            "gamma": 2.2,
            "fps_limit": 60,
        }
        if initial_settings:
            default_settings.update(initial_settings)
        self._settings = default_settings
        
        # Framebuffer queue (for future use if needed)
        self._framebuffer_queue: queue.Queue = queue.Queue()
    
    @property
    def status(self) -> VisualizationStatus:
        """Get current visualization status."""
        with self._lock:
            return self._status
    
    @property
    def is_running(self) -> bool:
        """Check if visualization is currently running."""
        return self.status == VisualizationStatus.RUNNING
    
    def start(self) -> bool:
        """
        Start the visualization system.
        
        Creates visualization window and runner, starts the render thread.
        Must be called from main thread (macOS requirement for window creation).
        
        Returns:
            True if started successfully, False otherwise
        """
        with self._lock:
            if self._status != VisualizationStatus.STOPPED:
                return False
            
            try:
                self._status = VisualizationStatus.STARTING
                
                # Create visualization window (must be on main thread)
                self._viz_window = VisualizationWindow(
                    width=self._width,
                    height=self._height,
                    scale=self._scale,
                    title="Cube Visualization",
                )
                
                # Create visualization runner
                self._viz_runner = VisualizationRunner(
                    width=self._width,
                    height=self._height,
                    num_panels=self._num_panels,
                    midi_state=self._midi_state,
                    usb_midi=self._usb_midi,
                    settings=self._settings,
                    viz_window=self._viz_window,
                    stop_callback=self._on_stop_callback,
                    framebuffer_queue=self._framebuffer_queue,
                )
                
                # Start visualization thread
                self._viz_runner.start()
                
                self._status = VisualizationStatus.RUNNING
                self._error_message = None
                return True
                
            except Exception as e:
                self._status = VisualizationStatus.ERROR
                self._error_message = str(e)
                return False
    
    def stop(self) -> bool:
        """
        Stop the visualization system.
        
        Stops the render thread and cleans up resources.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        with self._lock:
            if self._status == VisualizationStatus.STOPPED:
                return True
            
            if self._status == VisualizationStatus.STOPPING:
                return False
            
            try:
                self._status = VisualizationStatus.STOPPING
                
                if self._viz_runner:
                    # Signal stop (VisualizationRunner handles thread cleanup)
                    self._viz_runner._stop_flag.set()
                
                if self._viz_window:
                    self._viz_window.close()
                
                self._status = VisualizationStatus.STOPPED
                self._error_message = None
                return True
                
            except Exception as e:
                self._status = VisualizationStatus.ERROR
                self._error_message = str(e)
                return False
    
    def _on_stop_callback(self):
        """Callback from visualization thread when it stops."""
        with self._lock:
            if self._status == VisualizationStatus.RUNNING:
                self._status = VisualizationStatus.STOPPED
    
    def deploy_pipeline(
        self,
        source: Optional[Dict[str, Any]] = None,
        effects: Optional[List[Dict[str, Any]]] = None,
        pixel_mapper: str = "surface",
    ) -> bool:
        """
        Deploy or update the DAG pipeline.
        
        Args:
            source: Source configuration dict with 'shader_path' or 'video_path'
            effects: List of effect configurations with 'action' and 'enabled'
            pixel_mapper: Pixel mapper type ('cube' or 'surface')
        
        Returns:
            True if deployment queued successfully, False otherwise
        """
        with self._lock:
            if not self.is_running:
                return False
            
            if not self._viz_runner:
                return False
            
            try:
                source_config = source or {}
                source_config['pixel_mapper'] = pixel_mapper
                
                pipeline_config = {
                    'source': source_config,
                    'effects': effects or [],
                    'params': None,
                }
                
                self._viz_runner.deploy_pipeline(pipeline_config)
                return True
                
            except Exception as e:
                self._error_message = str(e)
                return False
    
    def set_parameter(self, name: str, value: Union[float, tuple, bool]) -> bool:
        """
        Update a single parameter value.
        
        Designed for high-frequency updates (120+ FPS). Updates are applied
        directly to the ParameterStore. The visualization thread samples the
        current value each frame.
        
        Args:
            name: Parameter name (e.g., 'iParam0', 'iTime', 'iMouse')
            value: Parameter value (float, tuple, or bool depending on parameter type)
        
        Returns:
            True if update applied successfully, False otherwise
        """
        if not self.is_running:
            return False
        
        if not self._viz_runner or not hasattr(self._viz_runner, '_parameter_store'):
            return False
        
        parameter_store = self._viz_runner._parameter_store
        if not parameter_store:
            return False
        
        try:
            # Direct update - visualization thread will sample this value
            parameter_store.set_parameter_value(name, value)
            return True
        except Exception as e:
            self._error_message = f"Error setting parameter {name}: {e}"
            return False
    
    def set_parameters(self, parameters: Dict[str, Union[float, tuple, bool]]) -> bool:
        """
        Batch update multiple parameters.
        
        More efficient than multiple set_parameter() calls for bulk updates.
        Updates are applied directly to the ParameterStore.
        
        Args:
            parameters: Dictionary mapping parameter names to values
        
        Returns:
            True if all updates applied successfully, False otherwise
        """
        if not self.is_running:
            return False
        
        if not self._viz_runner or not hasattr(self._viz_runner, '_parameter_store'):
            return False
        
        parameter_store = self._viz_runner._parameter_store
        if not parameter_store:
            return False
        
        try:
            # Direct updates - visualization thread will sample these values
            for name, value in parameters.items():
                parameter_store.set_parameter_value(name, value)
            return True
        except Exception as e:
            self._error_message = f"Error setting parameters: {e}"
            return False
    
    def enable_effect(self, action_name: str) -> bool:
        """
        Enable an effect by action name.
        
        Args:
            action_name: Action enum name (e.g., 'TOGGLE_GLITCH')
        
        Returns:
            True if effect enabled successfully, False otherwise
        """
        return self._toggle_effect(action_name, enabled=True)
    
    def disable_effect(self, action_name: str) -> bool:
        """
        Disable an effect by action name.
        
        Args:
            action_name: Action enum name (e.g., 'TOGGLE_GLITCH')
        
        Returns:
            True if effect disabled successfully, False otherwise
        """
        return self._toggle_effect(action_name, enabled=False)
    
    def _toggle_effect(self, action_name: str, enabled: bool) -> bool:
        """Internal method to toggle an effect."""
        with self._lock:
            if not self.is_running or not self._viz_runner:
                return False
            
            try:
                from cube.input.actions import Action
                action = Action[action_name]
                
                # Get current DAG and effect manager
                if not hasattr(self._viz_runner, '_dag') or not hasattr(self._viz_runner, '_effect_manager'):
                    return False
                
                dag = self._viz_runner._dag
                effect_manager = self._viz_runner._effect_manager
                
                if enabled:
                    effect_manager.trigger_effect(action, dag)
                else:
                    effect_manager.untoggle_effect(action, dag)
                
                return True
                
            except (KeyError, AttributeError) as e:
                self._error_message = f"Unknown effect action: {action_name}"
                return False
    
    def set_setting(self, name: str, value: Any) -> bool:
        """
        Update a visualization setting.
        
        Supported settings:
        - 'brightness': float (1.0-90.0)
        - 'gamma': float (0.5-3.0)
        - 'fps_limit': int (10-120)
        - 'viz_debug_ui': bool
        - 'debug_axes': bool
        
        Args:
            name: Setting name
            value: Setting value
        
        Returns:
            True if setting updated successfully, False otherwise
        """
        with self._lock:
            if name not in self._settings:
                return False
            
            # Validate value ranges
            if name == 'brightness' and (value < 1.0 or value > 90.0):
                return False
            if name == 'gamma' and (value < 0.5 or value > 3.0):
                return False
            if name == 'fps_limit' and (value < 10 or value > 120):
                return False
            
            self._settings[name] = value
            
            # Update runner settings if running
            if self._viz_runner and hasattr(self._viz_runner, '_settings'):
                self._viz_runner._settings[name] = value
            
            return True
    
    def get_setting(self, name: str) -> Optional[Any]:
        """
        Get a visualization setting value.
        
        Args:
            name: Setting name
        
        Returns:
            Setting value or None if not found
        """
        with self._lock:
            return self._settings.get(name)
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get all visualization settings.
        
        Returns:
            Dictionary of all settings
        """
        with self._lock:
            return self._settings.copy()
    
    def get_status_info(self) -> Dict[str, Any]:
        """
        Get comprehensive status information.
        
        Returns:
            Dictionary with status, error message, and current state
        """
        with self._lock:
            info = {
                'status': self._status.value,
                'is_running': self.is_running,
                'error': self._error_message,
                'settings': self.get_settings(),
            }
            
            # Add parameter info if available
            if self._viz_runner and hasattr(self._viz_runner, '_parameter_store'):
                param_store = self._viz_runner._parameter_store
                if param_store:
                    info['parameters'] = param_store.get_all_parameters()
            
            # Add active effects if available
            if self._viz_runner and hasattr(self._viz_runner, '_effect_manager'):
                effect_manager = self._viz_runner._effect_manager
                if effect_manager:
                    active_actions = effect_manager.get_active_actions()
                    info['active_effects'] = [action.name for action in active_actions]
            
            return info
    
    def cleanup(self):
        """Clean up resources."""
        self.stop()
        if self._viz_window:
            self._viz_window = None
        if self._viz_runner:
            self._viz_runner = None

