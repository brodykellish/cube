# Simplified Parameter Store for DAG Rendering

## Overview

Create a `ParameterStore` class that directly holds `Parameter` objects. Eliminate `ParameterRegistry` and `UniformSource` abstractions. Everything (camera, mouse, time, etc.) is just a `Parameter` in the store. Updaters (functions) update parameter values each frame.

## Architecture

```
ParameterStore (simple data store)
├── Dict[str, Parameter] - all parameters by name
└── set_parameter_value() - called by handlers to update parameters

ParameterHandler (abstract interface)
├── update(dt) - updates parameters in ParameterStore
└── get_name() - returns handler name for debugging

ParameterHandlerRegistry (central manager)
├── List[ParameterHandler] - all registered handlers
├── register(handler) - add a handler
└── update_all(dt) - updates all handlers in order

Concrete Handlers (implement ParameterHandler)
├── TimeHandler - updates iTime, iFrame, iTimeDelta
├── CameraHandler - updates camera vectors
├── MouseHandler - updates mouse state
├── SignalParameterHandler - updates parameter from any signal (LFO, audio, keyboard signals)
└── DirectParameterHandler - directly reads InputManager axis and updates parameter

DAGRenderer.render(dag, parameters)
├── For each node:
│   ├── Get node-specific parameters (add iResolution, iTime, etc.)
│   ├── Bind parameters to shader via uniforms
│   └── Render node
```

**Key Design**: 
- ParameterStore = data container (separate from handlers)
- ParameterHandlerRegistry = handler management (separate from data)
- All handlers implement `ParameterHandler` interface
- Handlers are updated in a loop via `handler_registry.update_all(dt)`

## Implementation Plan

### 1. Create `ParameterStore` class

**File**: `src/cube/render/parameter_store.py` (new file)

```python
from typing import Dict, Any, Optional, Callable
from cube.core.parameter import Parameter, ParameterType
import time

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
        # Time parameters (updated each frame by update_time_parameters())
        self.add_parameter(Parameter('iTime', ParameterType.FLOAT, 0.0))
        self.add_parameter(Parameter('iFrame', ParameterType.FLOAT, 0.0))
        self.add_parameter(Parameter('iTimeDelta', ParameterType.FLOAT, 0.016))
        
        # Camera parameters (updated by camera handler)
        self.add_parameter(Parameter('iCameraPos', ParameterType.VEC3, (0.0, 0.0, 0.0)))
        self.add_parameter(Parameter('iCameraRight', ParameterType.VEC3, (1.0, 0.0, 0.0)))
        self.add_parameter(Parameter('iCameraUp', ParameterType.VEC3, (0.0, 1.0, 0.0)))
        self.add_parameter(Parameter('iCameraForward', ParameterType.VEC3, (0.0, 0.0, 1.0)))
        
        # Mouse parameter (updated by mouse handler)
        self.add_parameter(Parameter('iMouse', ParameterType.VEC4, (0.0, 0.0, 0.0, 0.0)))
        
        # Parameter controls (updated by input handler via mappings)
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
    
    def get_parameters_for_node(self, node: Node) -> Dict[str, Any]:
        """
        Get parameters for a specific node, adding node-specific values.
        
        This is called by DAGRenderer to get uniforms for a node.
        """
        params = self.get_all_parameters()
        params['iResolution'] = (float(node.width), float(node.height), 1.0)
        return params
```

### 2. Create ParameterHandler abstraction and registry

**File**: `src/cube/render/parameter_store.py` (continued)

Define a clean abstraction for parameter handlers with a central registry.

```python
from abc import ABC, abstractmethod
from typing import List

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


class CameraHandler(ParameterHandler):
    """
    Handles camera updates and writes camera vectors to ParameterStore.
    """
    
    def __init__(self, parameter_store: ParameterStore, camera: CameraMode, input_manager: InputManager):
        self.parameter_store = parameter_store
        self.camera = camera
        self.input_manager = input_manager
        self.last_update_time = time.time()
        
        # Input state (can be set directly or derived from InputManager)
        self.input_state = {
            'left': 0.0, 'right': 0.0, 'up': 0.0, 'down': 0.0,
            'forward': 0.0, 'backward': 0.0
        }
        self.shift_pressed = False
    
    def set_key_state(self, key: str, pressed: bool):
        """Set camera input key state (called by input layer if needed)."""
        if key in self.input_state:
            self.input_state[key] = 1.0 if pressed else 0.0
        elif key == 'shift':
            self.shift_pressed = pressed
    
    def get_name(self) -> str:
        """Get handler name."""
        return "CameraHandler"
    
    def update(self, dt: float):
        """
        Update camera from InputManager and write vectors to ParameterStore.
        
        Called each frame before rendering.
        """
        # Read camera axes from InputManager
        from cube.input.actions import Axis
        
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


class TimeHandler(ParameterHandler):
    """
    Handles time-related parameter updates.
    """
    
    def __init__(self, parameter_store: ParameterStore):
        self.parameter_store = parameter_store
    
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
```

### 2b. Signal and Direct Parameter Handlers

**File**: `src/cube/render/parameter_store.py` (continued)

Unified handlers for signal-based and direct input-based parameter updates:

```python
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


class DirectParameterHandler(ParameterHandler):
    """
    Handler that directly reads from InputManager and updates a parameter.
    
    Used for MIDI overrides and simple axis→parameter mappings.
    """
    
    def __init__(
        self,
        parameter_store: ParameterStore,
        input_manager: InputManager,
        parameter_id: str,
        axis: Axis,
        priority: int = 100  # High priority - overrides signal handlers
    ):
        """
        Initialize direct parameter handler.
        
        Args:
            parameter_store: ParameterStore to update
            input_manager: InputManager to read from
            parameter_id: ID of parameter to update
            axis: Axis to read from InputManager
            priority: Handler priority (higher = updates later, can override earlier)
        """
        self.parameter_store = parameter_store
        self.input_manager = input_manager
        self.parameter_id = parameter_id
        self.axis = axis
        self.priority = priority
        self._enabled = True
    
    def get_name(self) -> str:
        """Get handler name."""
        return f"DirectParameterHandler({self.parameter_id} <- {self.axis.name})"
    
    def set_enabled(self, enabled: bool):
        """Enable or disable this handler."""
        self._enabled = enabled
    
    def update(self, dt: float):
        """
        Read from InputManager and update parameter.
        
        Called each frame before rendering. Only updates if axis value is >= 0.0.
        """
        if not self._enabled:
            return
        
        value = self.input_manager.get_axis(self.axis, -1.0)
        if value >= 0.0:
            self.parameter_store.set_parameter_value(self.parameter_id, value)
```


### 3. Update `DAGRenderer.render()` signature

**File**: `src/cube/render/dag_renderer.py`

```python
class DAGRenderer:
    def render(self, dag: DAG, parameters: ParameterStore) -> np.ndarray:
        """
        Render a DAG with parameters.
        
        Args:
            dag: DAG to render
            parameters: ParameterStore with all parameter values (already updated)
            
        Returns:
            Final framebuffer
            
        Note: Parameters should be updated BEFORE calling render().
        This method only reads from ParameterStore, it does not update it.
        """
        if not dag or not dag.nodes:
            raise RuntimeError("DAG is empty")
        
        # Render all nodes in topological order
        sorted_nodes = dag.topological_sort()
        
        for node in sorted_nodes:
            if not node.enabled:
                continue
            
            # Get parameters for this node
            node_params = parameters.get_parameters_for_node(node)
            resolution = (float(node.width), float(node.height))
            t = time.time() - parameters.start_time
            
            # Render node with parameters
            if isinstance(node, EffectNode):
                node.render(t, resolution, uniforms=node_params, dag=dag)
            elif isinstance(node, SourceNode):
                node.render(t, resolution, uniforms=node_params)
            elif isinstance(node, VideoSourceNode):
                node.render(t, resolution, uniforms=node_params)
            else:
                node.render(t, resolution)
        
        # ... rest of render logic for pixel mapping ...
```

### 4. Simplify `DAGRenderer.__init__`

**File**: `src/cube/render/dag_renderer.py`

- Remove all uniform source management
- Remove `_update_uniforms()` method
- Keep only OpenGL context setup and pixel mapping
```python
def __init__(self, 
             pixel_mapper: PixelMapper,
             make_context_current: Optional[Callable[[], bool]] = None):
    # ... OpenGL context setup ...
    # Note: parameters are passed to render(), not stored here
```


### 5. Update `VisualizationRunner` to create `ParameterStore` and wire input

**File**: `src/cube/render/visualization_runner.py`

Update `_run_loop()` to:
1. Create `ParameterStore` instance
2. Create input handlers (camera, mouse, parameters)
3. Update all handlers each frame (before rendering)
4. Pass `ParameterStore` to `DAGRenderer.render()` in render loop

**API Changes**:

```python
# In VisualizationRunner._run_loop():

# Create ParameterStore and HandlerRegistry
from cube.render.parameter_store import (
    ParameterStore, ParameterHandlerRegistry,
    CameraHandler, MouseHandler, TimeHandler,
    SignalParameterHandler, DirectParameterHandler
)
from cube.core.parameter_bridge import KeyboardParamSignal, AudioSignal, MIDISignal
from cube.core.signal import LFO
from cube.shader import SphericalCamera
from cube.input.actions import Axis, Action

parameter_store = ParameterStore(settings=self._settings)
handler_registry = ParameterHandlerRegistry()

# Create and register time handler
time_handler = TimeHandler(parameter_store)
handler_registry.register(time_handler)

# Create and register camera handler
camera = SphericalCamera()
camera_handler = CameraHandler(parameter_store, camera, self._viz_input_manager)
handler_registry.register(camera_handler)

# Create and register mouse handler
mouse_handler = MouseHandler(parameter_store, self._width, self._height)
handler_registry.register(mouse_handler)

# Create signal-based handlers for iParam0-7 (keyboard increment/decrement)
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
    
    # Audio signal handler (if mapped - highest priority)
    if audio_mapping_source:
        audio_mappings = audio_mapping_source.get_all_mappings()
        if audio_signal_name := audio_mappings.get(param_id):
            audio_signal = AudioSignal(audio_mapping_source, audio_signal_name)
            audio_handler = SignalParameterHandler(
                parameter_store,
                audio_signal,
                param_id,
                priority=200  # Highest priority - overrides MIDI and keyboard
            )
            handler_registry.register(audio_handler)
            # Disable keyboard handler when audio is mapped
            keyboard_handler.set_enabled(False)

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

# Example: Add LFO handler (unified with same abstraction)
lfo = LFO(frequency=0.5)  # 0.5 Hz oscillation
lfo_handler = SignalParameterHandler(
    parameter_store,
    lfo,
    'iParam0',
    transform=lambda x: (x + 1.0) / 2.0,  # Normalize [-1, 1] to [0, 1]
    priority=50  # Medium priority - overrides keyboard but not MIDI
)
# handler_registry.register(lfo_handler)  # Uncomment to enable

# In render loop (each frame):
# 1. Poll input (already done)
self._viz_input_manager.poll()

# 2. Update audio mapping source (if needed)
if audio_mapping_source:
    audio_mapping_source.update(dt)

# 3. Update all parameters via registry (independent of rendering)
dt = frame_time  # Calculate actual dt
handler_registry.update_all(dt)

# 4. Render (DAGRenderer just reads from ParameterStore)
framebuffer = self._renderer.render(self._dag, parameter_store)
```

**Key Design Points**:

1. **Input polling happens first** - `InputManager.poll()` reads raw input
2. **All parameter updates happen second** - Handlers update ParameterStore from their sources
3. **Rendering happens third** - DAGRenderer just reads from ParameterStore
4. **Clear separation**: Input → ParameterStore (via handlers) → Rendering (reads only)

This ensures:
- Input handling is independent of rendering
- Parameters are updated before rendering samples them
- ParameterStore is a simple data store (no update logic inside it)
- All update logic is in dedicated handlers

## Files to Create/Modify

1. **`src/cube/render/parameter_store.py`** (new): 
   - `ParameterStore` class (simple data container)
   - `ParameterHandler` abstract base class (defines handler interface)
   - `ParameterHandlerRegistry` class (manages all handlers, updates them in priority order)
   - `TimeHandler` class (updates time parameters)
   - `CameraHandler` class (updates camera, writes to ParameterStore)
   - `MouseHandler` class (updates mouse, writes to ParameterStore)
   - `SignalParameterHandler` class (updates parameter from any signal - LFO, audio, keyboard signals)
   - `DirectParameterHandler` class (directly reads InputManager axis and updates parameter)

2. **`src/cube/render/dag_renderer.py`**: 
   - Update `render(dag, parameters: ParameterStore)` signature
   - Remove uniform source management from `__init__`
   - Remove `_update_uniforms()` method
   - Remove `parameters.update(dt)` call (parameters are updated before render)
   - Use `parameters.get_parameters_for_node(node)` to get uniforms

3. **`src/cube/render/visualization_runner.py`**: 
   - Create `ParameterStore` and `ParameterHandlerRegistry` in `_run_loop()`
   - Create and register all handlers (`TimeHandler`, `CameraHandler`, `MouseHandler`, `ParameterInputHandler`)
   - Call `handler_registry.update_all(dt)` each frame (before rendering)
   - Pass `ParameterStore` to `DAGRenderer.render()`

4. **`src/cube/core/signal.py`**: 
   - Signals (LFO, MIDISignal, KeyboardParamSignal, AudioSignal) remain unchanged
   - Used by `SignalParameterHandler` to sample values

## Key Design Decisions

1. **No `ParameterRegistry`**: `ParameterStore` IS the registry - it holds parameters directly
2. **No `UniformSource`**: Everything is a `Parameter`, updated by handlers
3. **Simple ParameterStore**: Just a data container with `set_parameter_value()` - no update logic
4. **Clean handler abstraction**: `ParameterHandler` ABC defines the interface, all handlers implement it
5. **Central handler registry**: `ParameterHandlerRegistry` manages all handlers, updates them in a loop
6. **Separation of concerns**: 
   - `ParameterStore` = data container (separate from handlers)
   - `ParameterHandlerRegistry` = handler management (separate from data)
   - Handlers = update logic (implement `ParameterHandler` interface)
7. **Stateless renderer**: `DAGRenderer` doesn't store parameters, receives them as argument
8. **Clear separation**: Parameters = state, Uniforms = binding mechanism
9. **Input independence**: Input handling is separate from rendering:
   - InputManager polls raw input
   - Handlers convert InputManager state → ParameterStore (via `set_parameter_value()`)
   - DAGRenderer samples ParameterStore at render time (read-only)
10. **Unified signal abstraction**: All signal-based parameter control (LFOs, audio, keyboard signals) uses `SignalParameterHandler`
11. **Unified input abstraction**: All direct input→parameter mappings (MIDI, axes) use `DirectParameterHandler`
12. **Priority-based updates**: Handlers have priority - lower priority updates first, higher priority can override
13. **No separate MappingManager**: Signal→parameter mappings are just handlers in the registry
14. **Update order matters**: Handlers are updated in priority order (lower first, higher can override)
15. **Easy extensibility**: Add new handlers by implementing `ParameterHandler` and registering
16. **Consistent abstraction**: LFOs, audio signals, keyboard signals, MIDI - all use the same handler interface

## Future Extensibility

- **LFOs**: Create `LFO` signal → `SignalParameterHandler` → register in handler registry
- **External signals**: Create `ExternalSignal` → `SignalParameterHandler` → register in handler registry
- **Live remapping**: Enable/disable handlers at runtime via `handler.set_enabled(False)`
- **Node-specific parameters**: Future registration can filter parameters per node
- **Gamepad support**: Add gamepad input handler similar to camera handler
- **Touch input**: Add touch input handler similar to mouse handler
- **Multiple signals per parameter**: Register multiple handlers for same parameter with different priorities

## Complete Call Flow Example

```
Frame Start:
1. InputManager.poll()                    # Read raw keyboard/MIDI input

2. Update all parameters via registry (in priority order):
   └─ handler_registry.update_all(dt)    # Updates all handlers in priority order:
      ├─ TimeHandler.update()             # Update iTime, iFrame, iTimeDelta (priority 0)
      ├─ CameraHandler.update()          # Read InputManager → update camera → write to ParameterStore
      ├─ MouseHandler.update()            # Write mouse state to ParameterStore
      ├─ SignalParameterHandler (keyboard) # Keyboard increment/decrement (priority 0)
      ├─ DirectParameterHandler (MIDI)    # MIDI override (priority 100, overrides keyboard)
      └─ SignalParameterHandler (audio)   # Audio signals (priority 200, overrides MIDI)

3. Render (DAGRenderer just reads):
   └─ DAGRenderer.render(dag, parameters)
      └─ For each node:
         ├─ node_params = parameters.get_parameters_for_node(node)
         ├─ Add iResolution to node_params
         └─ node.render(uniforms=node_params) # Bind parameters as shader uniforms
```

This design ensures:
- **Input is independent**: Input handling doesn't know about rendering
- **Parameters are centralized**: All state in ParameterStore
- **ParameterStore is simple**: Just a data container, no update logic
- **Clean abstraction**: `ParameterHandler` ABC provides consistent interface
- **Centralized management**: `ParameterHandlerRegistry` manages all handlers
- **Update logic is external**: All handlers update parameters directly
- **Easy to extend**: Add new handlers by implementing `ParameterHandler`
- **Rendering is stateless**: DAGRenderer just reads from ParameterStore
- **Clear data flow**: Input → Handlers (via Registry) → ParameterStore → Rendering