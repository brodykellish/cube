# Camera Modes

The unified shader renderer supports multiple camera control schemes through an extensible camera mode system.

## Architecture

Camera modes are defined by the `CameraMode` abstract base class in `menu/camera_modes.py`. Each mode:
1. Maintains its own state (position, velocity, etc.)
2. Processes input and updates state
3. Computes camera vectors (position, right, up, forward)

This allows different navigation paradigms without modifying the shader renderer core.

## Current Camera Modes

### SphericalCamera (Default)

**Description**: Camera orbits around the origin using spherical coordinates (yaw, pitch, distance).

**Best for**:
- Viewing 3D objects/scenes from all angles
- Raymarching demos
- Scenes centered at the origin

**Controls**:
- **Left/Right (Arrow/A/D)**: Rotate yaw (horizontal)
- **Up/Down (Arrow/W/S)**: Rotate pitch (vertical)
- **Shift + Up/Down**: Zoom in/out (alternative to E/C)
- **E/C**: Zoom in/out
- **Forward/Backward**: Zoom in/out

**Features**:
- Smooth acceleration and damping
- No gimbal lock (proper spherical math)
- Full 360° rotation on all axes
- Frame-rate independent
- Configurable speeds and damping

**Parameters**:
```python
SphericalCamera(
    distance=12.0,        # Initial distance from origin
    yaw=0.785,            # Initial horizontal angle (radians, ~45°)
    pitch=0.6,            # Initial vertical angle (radians, ~34°)
    rotate_speed=1.5,     # Rotation speed (radians/sec)
    zoom_speed=5.0,       # Zoom speed (units/sec)
    damping=0.9,          # Velocity damping (0=instant stop, 1=no damping)
    min_distance=1.0,     # Minimum zoom distance
    max_distance=50.0     # Maximum zoom distance
)
```

**Math**:
- Position: `(r*cos(p)*sin(y), r*sin(p), r*cos(p)*cos(y))`
- Forward: Points toward origin (normalized)
- Right: Tangent to latitude circle
- Up: Tangent to longitude circle

## Future Camera Modes

### FPSCamera (Planned)

**Description**: First-person shooter style navigation with ground plane constraint.

**Best for**:
- Walking through 3D environments
- Architectural visualization
- Ground-level exploration

**Planned Controls**:
- **W/S**: Move forward/backward
- **A/D**: Strafe left/right
- **Mouse/Arrow**: Look around
- **Space/Shift**: Move up/down (fly mode)

**Features**:
- Maintains "up" direction (no rolling)
- Optional ground collision
- Walking vs flying modes
- Head bob (optional)

### FlyingCamera (Planned)

**Description**: Free-flying camera like a bird with banking on turns.

**Best for**:
- Flying through scenes
- Above-horizon navigation
- Cinematic movement

**Planned Controls**:
- **W/S**: Pitch up/down
- **A/D**: Bank/turn left/right
- **Arrow Up/Down**: Accelerate/decelerate
- **Q/E**: Roll left/right

**Features**:
- Banking on turns (realistic feel)
- Momentum-based movement
- Optional horizon constraint
- Smooth acceleration curves

## Using Camera Modes

### Setting Camera Mode

```python
from menu.camera_modes import SphericalCamera, FPSCamera

# During initialization
renderer = UnifiedShaderRenderer(64, 64)

# Switch to different mode (future)
renderer.set_camera_mode(FPSCamera())

# Reset camera to default position
renderer.reset_camera()
```

### In Controller

The controller automatically handles input and passes it to the camera mode:

```python
# In shader mode rendering loop
keys = pygame.key.get_pressed()

# Update shift modifier
self.shader_renderer.shift_pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

# Update input state (camera mode handles the rest)
self.shader_renderer.handle_input('up', keys[pygame.K_UP])
# ... etc
```

### From Shader

Shaders receive precomputed camera vectors regardless of mode:

```glsl
uniform vec3 iCameraPos;      // Camera position
uniform vec3 iCameraRight;    // Right vector
uniform vec3 iCameraUp;       // Up vector
uniform vec3 iCameraForward;  // Forward vector

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use camera vectors (works with any mode)
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // ... raymarching code
}
```

## Adding New Camera Modes

To add a new camera mode:

1. **Create class** inheriting from `CameraMode`
2. **Implement required methods**:
   - `update(input_state, dt, shift_pressed)` - Update camera state
   - `get_vectors()` - Return (pos, right, up, forward)
   - `reset()` - Reset to initial state

3. **Example skeleton**:

```python
class MyCameraMode(CameraMode):
    """Custom camera mode description."""

    def __init__(self, **params):
        super().__init__()
        # Initialize state variables
        self.position = [0, 0, 0]
        self.rotation = [0, 0, 0]
        # ... etc

    def update(self, input_state: Dict[str, float], dt: float, shift_pressed: bool = False):
        """Update camera based on input."""
        # Read input
        move_x = input_state['right'] - input_state['left']
        move_y = input_state['up'] - input_state['down']

        # Update state
        self.position[0] += move_x * dt
        self.position[1] += move_y * dt
        # ... etc

    def get_vectors(self) -> Tuple[Tuple[float, float, float], ...]:
        """Compute camera vectors."""
        pos = tuple(self.position)
        # Compute right, up, forward from rotation
        right = (1, 0, 0)  # ... actual math
        up = (0, 1, 0)     # ... actual math
        forward = (0, 0, -1)  # ... actual math
        return pos, right, up, forward

    def reset(self):
        """Reset to initial state."""
        self.position = [0, 0, 0]
        self.rotation = [0, 0, 0]
```

4. **Add to `camera_modes.py`**
5. **Use in renderer**:
```python
renderer.set_camera_mode(MyCameraMode())
```

## Design Principles

1. **Separation of concerns**: Camera logic separate from rendering
2. **Mode independence**: Shaders work with any camera mode
3. **Smooth transitions**: Can switch modes mid-flight (future)
4. **Consistent interface**: All modes use same input/output format
5. **Extensibility**: Easy to add new modes without touching core

## Benefits

- **Different shaders need different cameras**: Architectural scenes need FPS, space scenes need spherical
- **User preference**: Some users prefer different controls
- **Game controller support**: Different modes map better to different input devices
- **Scene-specific**: Auto-switch based on shader metadata (future)

## Testing Camera Modes

To test a camera mode:

1. Load any shader in cube control
2. Use keyboard controls to navigate
3. Verify smooth motion and correct vectors
4. Test edge cases (gimbal lock, extreme distances, etc.)

## See Also

- `menu/camera_modes.py` - Camera mode implementations
- `menu/unified_shader_renderer.py` - Renderer integration
- `docs/SHADER_INPUT.md` - Input system documentation
