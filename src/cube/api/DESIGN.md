# Visualization API Design

## Overview

The Visualization API provides a clean, thread-safe interface for managing visualizations, parameters, effects, and DAG pipelines. It is designed as a bridge between web API handlers (Flask) and the core visualization system.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Web API Layer                      │
│  (HTTP endpoints for starting/stopping, parameter updates)  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Uses
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              VisualizationAPI (cube/api/)                   │
│  - Thread-safe operations                                   │
│  - Parameter update queue                                    │
│  - Status management                                         │
│  - Settings management                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Wraps
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         VisualizationRunner (cube/render/)                  │
│  - Render thread management                                  │
│  - DAG pipeline deployment                                   │
│  - Effect management                                         │
│  - Parameter store                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Uses
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         Core Visualization Components                       │
│  - DAGRenderer, EffectManager, ParameterStore               │
│  - SourceNode, EffectNode                                    │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Thread Safety

All API operations are thread-safe using:
- `threading.RLock()` for state management
- `queue.Queue()` for cross-thread communication
- Status-based state machine for lifecycle management

### 2. High-Frequency Parameter Updates

Parameter updates are designed for 120+ FPS:
- Updates are applied directly to `ParameterStore`
- Visualization thread samples current values each frame
- Independent update and read cycles (no queue)
- Always uses the most recent parameter value
- Batch updates supported via `set_parameters()`

### 3. Minimal API Surface

The API exposes only essential operations:
- Lifecycle: `start()`, `stop()`, `cleanup()`
- Pipeline: `deploy_pipeline()`
- Parameters: `set_parameter()`, `set_parameters()`
- Effects: `enable_effect()`, `disable_effect()`
- Settings: `set_setting()`, `get_setting()`, `get_settings()`
- Status: `status`, `is_running`, `get_status_info()`

### 4. Clean Abstraction

The API hides implementation details:
- VisualizationRunner thread management
- Queue-based communication
- Parameter store internals
- Effect manager details

### 5. Separation of Concerns

- **VisualizationAPI**: Public interface, thread safety, status tracking
- **VisualizationRunner**: Render thread, DAG management, effect processing
- **ParameterStore**: Parameter storage and validation
- **EffectManager**: Effect lifecycle and DAG integration

## Data Flow

### Parameter Updates

```
Web API Handler
    │
    │ set_parameter('iParam0', 0.75)
    ▼
VisualizationAPI
    │
    │ Direct update
    ▼
ParameterStore.set_parameter_value()
    │
    │ (stored value)
    │
    │ Sampled each frame
    ▼
VisualizationRunner (render loop)
    │
    │ get_parameters_for_node()
    ▼
DAGRenderer.render()
```

**Key Design**: Parameter updates and visualization reads happen on independent clock cycles. The visualization thread samples the current parameter value each frame, ensuring the most recent value is always used.

### Pipeline Deployment

```
Web API Handler
    │
    │ deploy_pipeline(source, effects)
    ▼
VisualizationAPI
    │
    │ Queue pipeline config
    ▼
VisualizationRunner._pipeline_queue
    │
    │ Processed in render loop
    ▼
VisualizationRunner._deploy_pipeline_internal()
    │
    │ Create/update DAG nodes
    ▼
DAG + EffectManager
```

### Effect Management

```
Web API Handler
    │
    │ enable_effect('TOGGLE_GLITCH')
    ▼
VisualizationAPI
    │
    │ Direct call (thread-safe)
    ▼
EffectManager.trigger_effect()
    │
    │ Modify DAG
    ▼
DAG (add effect nodes)
```

## Status Management

The API uses a state machine for lifecycle management:

```
STOPPED ──start()──> STARTING ──> RUNNING
   ▲                                    │
   │                                    │ stop()
   └───────────────<───────────────────┘
                    STOPPING
```

Error states:
- `ERROR`: Set when operations fail
- Error message stored in `_error_message`
- Status can be queried via `get_status_info()`

## Parameter Update Queue

The parameter update queue is designed for high-frequency updates:

- **Queue Type**: `queue.Queue()` (unbounded, thread-safe)
- **Update Format**: `ParameterUpdate` dataclass or dict
- **Processing**: Every frame in render loop
- **Non-blocking**: Uses `get_nowait()` to avoid frame drops
- **Batch Support**: `set_parameters()` for multiple updates

## Settings Management

Settings are stored in `_settings` dict and synchronized:
- API maintains local copy
- VisualizationRunner receives settings on initialization
- Settings can be updated at runtime via `set_setting()`
- Changes take effect immediately

## Error Handling

The API uses a status-based error model:
- Methods return `bool` (True = success, False = failure)
- Errors stored in `_error_message`
- Status set to `ERROR` on failure
- Error info available via `get_status_info()`

## Future Extensions

The API is designed to be extensible:

1. **WebSocket Support**: Parameter updates could be streamed via WebSocket
2. **Parameter Subscriptions**: Clients could subscribe to parameter changes
3. **Pipeline Templates**: Save/load common pipeline configurations
4. **Effect Presets**: Save/load effect combinations
5. **Performance Metrics**: Expose FPS, frame times, etc.

## Testing Considerations

The API is designed for testability:
- Dependency injection (MIDI state, settings)
- Status-based state machine (easy to verify)
- Queue-based communication (can be mocked)
- Clean separation of concerns (unit testable)

## Performance Characteristics

- **Parameter Updates**: < 1ms per update (queue-based)
- **Pipeline Deployment**: ~10-50ms (depends on shader compilation)
- **Effect Toggle**: ~1-5ms (DAG modification)
- **Settings Update**: < 1ms (dict update)

All operations are non-blocking for the calling thread.

