"""
Parameter store and handler system for cube.

Provides a centralized parameter store and handler registry for updating
parameters from various sources (input, signals, time, camera, mouse).
"""
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Union
from cube.core.parameter import Parameter, ParameterType
from cube.core.signal import Signal
from cube.input.input_manager import InputManager
from cube.input.actions import Axis
from cube.shader.camera_modes import CameraMode


class ParameterStore:
    """
    Central store for all shader parameters.
    
    This is a simple data container - it does NOT update parameters itself.
    All updates are done by external handlers that call set_parameter_value().
    """
    
    def __init__(self, settings: Optional[Dict] = None):
        self._parameters: Dict[str, Parameter] = {}
        self.settings = settings or {}
        self.start_time = time.time()
        self.frame_count = 0
        
        # Initialize standard parameters
        self._init_standard_parameters()
    
    def _init_standard_parameters(self):
        """Initialize standard shader parameters."""
        # Time parameters (updated each frame by TimeHandler)
        self.add_parameter(Parameter('iTime', ParameterType.FLOAT, 0.0))
        self.add_parameter(Parameter('iFrame', ParameterType.FLOAT, 0.0))
        self.add_parameter(Parameter('iTimeDelta', ParameterType.FLOAT, 0.016))
        
        # Camera parameters (updated by CameraHandler)
        self.add_parameter(Parameter('iCameraPos', ParameterType.VEC3, (0.0, 0.0, 0.0)))
        self.add_parameter(Parameter('iCameraRight', ParameterType.VEC3, (1.0, 0.0, 0.0)))
        self.add_parameter(Parameter('iCameraUp', ParameterType.VEC3, (0.0, 1.0, 0.0)))
        self.add_parameter(Parameter('iCameraForward', ParameterType.VEC3, (0.0, 0.0, 1.0)))
        
        # Mouse parameter (updated by MouseHandler)
        self.add_parameter(Parameter('iMouse', ParameterType.VEC4, (0.0, 0.0, 0.0, 0.0)))
        
        # Parameter controls (updated by signal/direct handlers)
        for i in range(8):
            self.add_parameter(Parameter(f'iParam{i}', ParameterType.FLOAT, 0.0, min=0.0, max=1.0))
        self.add_parameter(Parameter('iSeed', ParameterType.FLOAT, 0.0))
        self.add_parameter(Parameter('iBeatPulse', ParameterType.FLOAT, 0.0))
        self.add_parameter(Parameter('iBeatPhase', ParameterType.FLOAT, 0.0))
        
        # Settings
        self.add_parameter(Parameter('iDebugAxes', ParameterType.FLOAT, 0.0))
    
    def add_parameter(self, parameter: Parameter):
        """Add a parameter to the store."""
        self._parameters[parameter.id] = parameter
    
    def get_parameter(self, id: str) -> Optional[Parameter]:
        """Get a parameter by ID."""
        return self._parameters.get(id)
    
    def set_parameter_value(self, id: str, value: Any):
        """
        Set a parameter value directly.
        
        This is called by input handlers to update parameters.
        The parameter will be clamped if it has min/max constraints.
        """
        if param := self.get_parameter(id):
            param.value = value
            param.clamp()
    
    def get_all_parameters(self) -> Dict[str, Any]:
        """Get all parameter values as a dictionary."""
        return {id: param.value for id, param in self._parameters.items()}
    
    def get_parameters_for_node(self, node) -> Dict[str, Any]:
        """
        Get parameters for a specific node, adding node-specific values.
        
        This is called by DAGRenderer to get uniforms for a node.
        """
        params = self.get_all_parameters()
        params['iResolution'] = (float(node.width), float(node.height), 1.0)
        return params


class ParameterHandler(ABC):
    """
    Abstract base class for all parameter handlers.
    
    Handlers read from input sources and update parameters in ParameterStore.
    All handlers implement the same interface for easy management.
    """
    
    @abstractmethod
    def update(self, dt: float) -> None:
        """
        Update parameters in ParameterStore.
        
        Called each frame before rendering. Handlers should read from their
        input sources and call parameter_store.set_parameter_value() to update.
        
        Args:
            dt: Delta time since last update (seconds)
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get handler name for debugging/logging.
        
        Returns:
            Handler name (e.g., "CameraHandler", "MouseHandler")
        """
        pass


class ParameterHandlerRegistry:
    """
    Central registry for all parameter handlers.
    
    Manages all handlers and provides a single update() method that updates
    all registered handlers. Handlers are updated in priority order (lower priority first),
    allowing higher priority handlers to override earlier updates.
    """
    
    def __init__(self):
        """Initialize handler registry."""
        self._handlers: List[ParameterHandler] = []
    
    def register(self, handler: ParameterHandler):
        """
        Register a parameter handler.
        
        Args:
            handler: ParameterHandler instance to register
            
        Note: Handlers must have a `priority` attribute. If not present, defaults to 0.
        Handlers are sorted by priority (lower first) so higher priority handlers
        can override earlier updates.
        """
        self._handlers.append(handler)
        # Sort by priority (lower priority updates first)
        self._handlers.sort(key=lambda h: getattr(h, 'priority', 0))
    
    def unregister(self, handler: ParameterHandler):
        """
        Unregister a parameter handler.
        
        Args:
            handler: ParameterHandler instance to unregister
        """
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def update_all(self, dt: float):
        """
        Update all registered handlers in priority order.
        
        Called each frame before rendering. Updates handlers in priority order
        (lower priority first), allowing higher priority handlers to override.
        
        Args:
            dt: Delta time since last update (seconds)
        """
        for handler in self._handlers:
            try:
                handler.update(dt)
            except Exception as e:
                print(f"[ParameterHandlerRegistry] Error updating {handler.get_name()}: {e}")
                import traceback
                traceback.print_exc()
    
    def get_handlers(self) -> List[ParameterHandler]:
        """Get all registered handlers (sorted by priority)."""
        return self._handlers.copy()
    
    def clear(self):
        """Clear all registered handlers."""
        self._handlers.clear()
    
    def get_handlers_for_parameter(self, parameter_id: str) -> List[ParameterHandler]:
        """
        Get all handlers that update a specific parameter.
        
        Args:
            parameter_id: Parameter ID to find handlers for
            
        Returns:
            List of handlers that update this parameter
        """
        handlers = []
        for handler in self._handlers:
            if hasattr(handler, 'parameter_id') and handler.parameter_id == parameter_id:
                handlers.append(handler)
        return handlers


class TimeHandler(ParameterHandler):
    """
    Handles time-related parameter updates.
    """
    
    def __init__(self, parameter_store: ParameterStore):
        self.parameter_store = parameter_store
        self.priority = 0
    
    def get_name(self) -> str:
        """Get handler name."""
        return "TimeHandler"
    
    def update(self, dt: float):
        """
        Update time-related parameters in ParameterStore.
        
        Called each frame before rendering.
        """
        elapsed = time.time() - self.parameter_store.start_time
        self.parameter_store.set_parameter_value('iTime', elapsed)
        self.parameter_store.set_parameter_value('iFrame', float(self.parameter_store.frame_count))
        self.parameter_store.set_parameter_value('iTimeDelta', dt)
        self.parameter_store.frame_count += 1


class CameraHandler(ParameterHandler):
    """
    Handles camera updates and writes camera vectors to ParameterStore.
    """
    
    def __init__(self, parameter_store: ParameterStore, camera: CameraMode, input_manager: InputManager):
        self.parameter_store = parameter_store
        self.camera = camera
        self.input_manager = input_manager
        self.last_update_time = time.time()
        self.priority = 0
        
        # Input state (can be set directly or derived from InputManager)
        self.input_state = {
            'left': 0.0, 'right': 0.0, 'up': 0.0, 'down': 0.0,
            'forward': 0.0, 'backward': 0.0
        }
        self.shift_pressed = False
    
    def get_name(self) -> str:
        """Get handler name."""
        return "CameraHandler"
    
    def set_key_state(self, key: str, pressed: bool):
        """Set camera input key state (called by input layer if needed)."""
        if key in self.input_state:
            self.input_state[key] = 1.0 if pressed else 0.0
        elif key == 'shift':
            self.shift_pressed = pressed
    
    def update(self, dt: float):
        """
        Update camera from InputManager and write vectors to ParameterStore.
        
        Called each frame before rendering.
        """
        # Read camera axes from InputManager
        pitch = self.input_manager.get_axis(Axis.CAMERA_PITCH, 0.0)
        yaw = self.input_manager.get_axis(Axis.CAMERA_YAW, 0.0)
        zoom = self.input_manager.get_axis(Axis.CAMERA_ZOOM, 0.0)
        roll = self.input_manager.get_axis(Axis.CAMERA_ROLL, 0.0)
        
        # Map axes to discrete input_state
        threshold = 0.1
        self.input_state['up'] = 1.0 if pitch > threshold else 0.0
        self.input_state['down'] = 1.0 if pitch < -threshold else 0.0
        self.input_state['right'] = 1.0 if yaw > threshold else 0.0
        self.input_state['left'] = 1.0 if yaw < -threshold else 0.0
        self.input_state['forward'] = 1.0 if zoom > threshold else 0.0
        self.input_state['backward'] = 1.0 if zoom < -threshold else 0.0
        
        # Roll: treat as shift+left/right
        if abs(roll) > threshold:
            self.input_state['right'] = 1.0 if roll > threshold else 0.0
            self.input_state['left'] = 1.0 if roll < -threshold else 0.0
            self.shift_pressed = True
        else:
            self.shift_pressed = False
        
        # Update camera
        self.camera.update(self.input_state, dt, self.shift_pressed)
        
        # Write camera vectors to ParameterStore
        pos, right, up, forward = self.camera.get_vectors()
        self.parameter_store.set_parameter_value('iCameraPos', pos)
        self.parameter_store.set_parameter_value('iCameraRight', right)
        self.parameter_store.set_parameter_value('iCameraUp', up)
        self.parameter_store.set_parameter_value('iCameraForward', forward)


class MouseHandler(ParameterHandler):
    """
    Handles mouse updates and writes mouse state to ParameterStore.
    """
    
    def __init__(self, parameter_store: ParameterStore, width: int, height: int):
        self.parameter_store = parameter_store
        self.width = width
        self.height = height
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.click_x = 0.0
        self.click_y = 0.0
        self.button_pressed = False
        self.priority = 0
    
    def get_name(self) -> str:
        """Get handler name."""
        return "MouseHandler"
    
    def set_position(self, x: float, y: float):
        """Set mouse position (called by window/backend)."""
        self.mouse_x = x
        self.mouse_y = y
    
    def set_button(self, pressed: bool):
        """Set mouse button state (called by window/backend)."""
        if pressed and not self.button_pressed:
            # Button just pressed - record click position
            self.click_x = self.mouse_x
            self.click_y = self.mouse_y
        elif not pressed:
            # Button released - clear click position
            self.click_x = 0.0
            self.click_y = 0.0
        self.button_pressed = pressed
    
    def update(self, dt: float):
        """
        Write mouse state to ParameterStore.
        
        Called each frame before rendering.
        """
        self.parameter_store.set_parameter_value('iMouse', (self.mouse_x, self.mouse_y, self.click_x, self.click_y))


class SignalParameterHandler(ParameterHandler):
    """
    Handler that updates a parameter from a signal.
    
    This unifies signal-based parameter control (LFOs, audio, keyboard signals)
    with the same handler abstraction. Each signal→parameter mapping becomes
    a handler that can be registered in the handler registry.
    """
    
    def __init__(
        self,
        parameter_store: ParameterStore,
        signal: Signal,
        parameter_id: str,
        transform: Optional[Callable[[float], float]] = None,
        priority: int = 0
    ):
        """
        Initialize signal parameter handler.
        
        Args:
            parameter_store: ParameterStore to update
            signal: Signal to sample (LFO, AudioSignal, KeyboardParamSignal, etc.)
            parameter_id: ID of parameter to update
            transform: Optional function to transform signal value
            priority: Handler priority (higher = updates later, can override earlier)
        """
        self.parameter_store = parameter_store
        self.signal = signal
        self.parameter_id = parameter_id
        self.transform = transform or (lambda x: x)
        self.priority = priority
        self._enabled = True
    
    def get_name(self) -> str:
        """Get handler name."""
        signal_type = type(self.signal).__name__
        return f"SignalParameterHandler({self.parameter_id} <- {signal_type})"
    
    def set_enabled(self, enabled: bool):
        """Enable or disable this handler."""
        self._enabled = enabled
    
    def update(self, dt: float):
        """
        Sample signal and update parameter.
        
        Called each frame before rendering.
        """
        if not self._enabled:
            return
        
        param = self.parameter_store.get_parameter(self.parameter_id)
        if param is None:
            return
        
        t = time.time()
        signal_value = self.signal.sample(t)
        transformed_value = self.transform(signal_value)
        
        if param.type.value == 'float':
            param.value = transformed_value
            param.clamp()
        elif param.type.value == 'bool':
            param.value = transformed_value > 0.5
        else:
            param.value = transformed_value


class SettingsParameterHandler(ParameterHandler):
    """
    Handler that updates parameters from settings dictionary.
    
    Used for settings-driven parameters like iDebugAxes.
    """
    
    def __init__(
        self,
        parameter_store: ParameterStore,
        settings: Dict[str, Any],
        parameter_id: str,
        settings_key: str,
        transform: Optional[Callable[[Any], Any]] = None,
        priority: int = 0
    ):
        """
        Initialize settings parameter handler.
        
        Args:
            parameter_store: ParameterStore to update
            settings: Settings dictionary
            parameter_id: ID of parameter to update
            settings_key: Key in settings dictionary
            transform: Optional function to transform settings value
            priority: Handler priority
        """
        self.parameter_store = parameter_store
        self.settings = settings
        self.parameter_id = parameter_id
        self.settings_key = settings_key
        self.transform = transform or (lambda x: x)
        self.priority = priority
    
    def get_name(self) -> str:
        """Get handler name."""
        return f"SettingsParameterHandler({self.parameter_id} <- settings.{self.settings_key})"
    
    def update(self, dt: float):
        """
        Read from settings and update parameter.
        
        Called each frame before rendering.
        """
        value = self.settings.get(self.settings_key)
        if value is not None:
            transformed_value = self.transform(value)
            self.parameter_store.set_parameter_value(self.parameter_id, transformed_value)

