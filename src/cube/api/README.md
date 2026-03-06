# Visualization API

Core API for managing visualizations, parameters, effects, and DAG pipelines.

## Overview

The `VisualizationAPI` class provides a thread-safe, high-performance interface for:
- Starting and stopping visualizations
- Deploying and updating DAG pipelines
- High-frequency parameter updates (120+ FPS)
- Effect management (enable/disable)
- Visualization settings (brightness, gamma, FPS)

## Design Principles

- **Minimal API surface**: Simple, focused methods
- **Thread-safe**: All operations are safe for concurrent access
- **High-performance**: Parameter updates designed for 120+ FPS
- **Clean abstraction**: Hides implementation details of VisualizationRunner

## Usage

### Basic Setup

```python
from cube.api.visualization_api import VisualizationAPI
from cube.midi.midi_state import MIDIState

# Initialize API
api = VisualizationAPI(
    width=64,
    height=64,
    num_panels=6,
    scale=1,
    midi_state=MIDIState(num_channels=8),
)

# Start visualization (must be called from main thread on macOS)
api.start()
```

### Deploying a Pipeline

```python
# Deploy a shader-based visualization
api.deploy_pipeline(
    source={'shader_path': 'shaders/effects/glitch.glsl'},
    effects=[],
    pixel_mapper='cube'
)

# Deploy a video source
api.deploy_pipeline(
    source={'video_path': 'videos/example.mp4'},
    effects=[
        {'action': 'TOGGLE_GLITCH', 'enabled': True},
        {'action': 'TOGGLE_BULGE', 'enabled': False},
    ],
    pixel_mapper='surface'
)
```

### High-Frequency Parameter Updates

Parameters are updated directly to the ParameterStore, and the visualization thread samples the current value each frame. This allows independent update and read cycles for maximum performance.

```python
# Update a single parameter (designed for 120+ FPS)
api.set_parameter('iParam0', 0.75)
api.set_parameter('iMouse', (0.5, 0.5, 0.0, 0.0))

# Batch update multiple parameters
api.set_parameters({
    'iParam0': 0.5,
    'iParam1': 0.8,
    'iTime': 123.45,
})
```

**Note**: Parameter updates are applied immediately. The visualization thread samples the current parameter values each frame, ensuring the most recent values are always used.

### Effect Management

```python
# Enable an effect
api.enable_effect('TOGGLE_GLITCH')

# Disable an effect
api.disable_effect('TOGGLE_BULGE')
```

### Settings Management

```python
# Update individual settings
api.set_setting('brightness', 80.0)
api.set_setting('gamma', 2.4)
api.set_setting('fps_limit', 120)

# Get settings
brightness = api.get_setting('brightness')
all_settings = api.get_settings()
```

### Status and Monitoring

```python
# Check status
status = api.status
is_running = api.is_running

# Get comprehensive status info
info = api.get_status_info()
# Returns:
# {
#     'status': 'running',
#     'is_running': True,
#     'error': None,
#     'settings': {...},
#     'parameters': {...},
#     'active_effects': [...]
# }
```

### Cleanup

```python
# Stop and cleanup
api.stop()
api.cleanup()
```

## API Reference

### VisualizationAPI

#### Methods

- `start() -> bool`: Start the visualization system
- `stop() -> bool`: Stop the visualization system
- `deploy_pipeline(source, effects, pixel_mapper) -> bool`: Deploy/update DAG pipeline
- `set_parameter(name, value) -> bool`: Update a single parameter
- `set_parameters(parameters) -> bool`: Batch update parameters
- `enable_effect(action_name) -> bool`: Enable an effect
- `disable_effect(action_name) -> bool`: Disable an effect
- `set_setting(name, value) -> bool`: Update a setting
- `get_setting(name) -> Any`: Get a setting value
- `get_settings() -> Dict`: Get all settings
- `get_status_info() -> Dict`: Get comprehensive status
- `cleanup()`: Clean up resources

#### Properties

- `status: VisualizationStatus`: Current visualization status
- `is_running: bool`: Whether visualization is running

### Parameter Types

Parameters support the following types:
- `float`: Single float value (e.g., `iTime`, `iParam0`)
- `tuple`: Vector values (e.g., `iMouse` as `(x, y, click_x, click_y)`)
- `bool`: Boolean values

### Supported Settings

- `brightness`: float (1.0-90.0) - Display brightness percentage
- `gamma`: float (0.5-3.0) - Gamma correction value
- `fps_limit`: int (10-120) - Target frames per second
- `viz_debug_ui`: bool - Enable debug UI overlay
- `debug_axes`: bool - Enable debug axes display

### Effect Actions

Effects are identified by `Action` enum names. Common examples:
- `TOGGLE_GLITCH`
- `TOGGLE_BULGE`
- `TOGGLE_SWIRL`
- `TOGGLE_INVERT`
- `TOGGLE_KALEIDOSCOPE`

See `effects_config.yml` for the full list of available effects.

## Thread Safety

All API methods are thread-safe and can be called from any thread, including:
- Web API request handlers (Flask)
- Background threads
- Main thread

Parameter updates are queued and processed in the visualization render thread, ensuring smooth 120+ FPS updates without blocking.

## Performance Considerations

- **Parameter Updates**: Designed for high-frequency updates (120+ FPS). Updates are queued and processed asynchronously.
- **Pipeline Deployment**: Pipeline changes are queued and applied atomically in the render thread.
- **Effect Toggles**: Effect enable/disable operations are thread-safe but may take a frame to apply.

## Error Handling

The API uses a status-based error model:
- Check `api.status` for current state
- Check `api.get_status_info()['error']` for error messages
- Methods return `False` on failure, `True` on success

## Integration with VisualizationRunner

The `VisualizationAPI` wraps `VisualizationRunner` and provides a cleaner interface:
- Hides thread management details
- Provides queue-based parameter updates
- Simplifies effect and pipeline management
- Adds status tracking and error handling

The API maintains a reference to `VisualizationRunner` internally and coordinates all operations through thread-safe queues and callbacks.

