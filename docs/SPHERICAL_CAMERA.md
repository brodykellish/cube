# Spherical Camera System - Smooth 360° Rotation

This document describes the spherical coordinate camera system that provides smooth, discontinuity-free rotation around a target point (origin).

## Overview

The camera uses **spherical coordinates** (distance, yaw, pitch) and computes orientation vectors using the **natural tangent basis** of the spherical coordinate system. This approach eliminates gimbal lock and provides perfectly smooth rotation at all angles.

## Mathematics

### Spherical Coordinates

```python
# Camera state
camera_distance = 8.0    # r: distance from origin
camera_yaw = 0.0         # θ (theta): horizontal angle
camera_pitch = 0.0       # φ (phi): vertical angle
```

### Position (Cartesian)

```python
x = distance * cos(pitch) * sin(yaw)
y = distance * sin(pitch)
z = distance * cos(pitch) * cos(yaw)
```

### Orientation Vectors

The key insight: use **partial derivatives** of the position as camera basis vectors!

**Forward** (toward origin):
```python
forward = normalize(-position)
```

**Right** (tangent to latitude circle, ∂position/∂yaw):
```python
right = [cos(yaw), 0, -sin(yaw)]
```
- Continuous everywhere
- Always horizontal
- Already unit length

**Up** (tangent to meridian, ∂position/∂pitch):
```python
up = [-sin(pitch)*sin(yaw), cos(pitch), -sin(pitch)*cos(yaw)]
```
- Continuous everywhere
- Already unit length (from trig identities: sin²+cos²=1)
- Naturally perpendicular to both forward and right

### Why This Works

1. **No cross products**: We avoid the singularities that occur when vectors become parallel
2. **No conditional logic**: No special cases for poles or other angles
3. **Natural basis**: The tangent vectors to spherical coordinates are inherently smooth and perpendicular
4. **Already normalized**: Mathematical properties ensure unit length without explicit normalization

## Implementation

### Python Renderer (`preview_renderer.py`)

**State variables:**
```python
self.camera_distance = 8.0
self.camera_yaw = 0.0
self.camera_pitch = 0.0

self.camera_distance_vel = 0.0
self.camera_yaw_vel = 0.0
self.camera_pitch_vel = 0.0
```

**Physics parameters:**
```python
self.camera_rotate_speed = 1.5   # Radians/second
self.camera_zoom_speed = 5.0     # Units/second
self.camera_damping = 0.9        # Velocity decay
```

**Key function** (`get_camera_vectors()`):
```python
def get_camera_vectors(self):
    """Compute camera position and orientation vectors from spherical coordinates."""
    import math

    # Position
    x = self.camera_distance * math.cos(self.camera_pitch) * math.sin(self.camera_yaw)
    y = self.camera_distance * math.sin(self.camera_pitch)
    z = self.camera_distance * math.cos(self.camera_pitch) * math.cos(self.camera_yaw)
    pos = [x, y, z]

    # Forward (toward origin)
    forward = [-x, -y, -z]
    f_len = math.sqrt(forward[0]**2 + forward[1]**2 + forward[2]**2)
    forward = [forward[0]/f_len, forward[1]/f_len, forward[2]/f_len]

    # Right (tangent to latitude)
    right = [math.cos(self.camera_yaw), 0.0, -math.sin(self.camera_yaw)]

    # Up (tangent to meridian)
    up = [
        -math.sin(self.camera_pitch) * math.sin(self.camera_yaw),
        math.cos(self.camera_pitch),
        -math.sin(self.camera_pitch) * math.cos(self.camera_yaw)
    ]

    return pos, right, up, forward
```

### Shader Uniforms

```glsl
uniform vec3 iCameraPos;      // Camera position
uniform vec3 iCameraRight;    // Right vector (precomputed)
uniform vec3 iCameraUp;       // Up vector (precomputed)
uniform vec3 iCameraForward;  // Forward vector (precomputed)
```

### Shader Usage

```glsl
void mainImage(out vec4 fragColor, vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use precomputed camera basis
    vec3 cameraPos = iCameraPos;
    vec3 right = iCameraRight;
    vec3 up = iCameraUp;
    vec3 forward = iCameraForward;

    // Ray direction
    vec3 rd = normalize(uv.x * right + uv.y * up + 1.5 * forward);

    // Your rendering code here...
}
```

## Controls

### Keyboard Mapping

| Keys | Action | Velocity Component |
|------|--------|-------------------|
| Left/Right (A/D) | Rotate horizontally (yaw) | `camera_yaw_vel` |
| Up/Down (W/S) | Rotate vertically (pitch) | `camera_pitch_vel` |
| Shift+Up/Down | Zoom in/out (distance) | `camera_distance_vel` |
| PageUp/Down (E/C) | Zoom in/out (distance) | `camera_distance_vel` |

### Input Processing

```python
# Left/Right: rotate yaw
self.camera_yaw_vel += input_lr * self.camera_rotate_speed * accel * dt

# Up/Down: behavior depends on shift
if self.shift_pressed:
    # Zoom
    self.camera_distance_vel -= input_ud * self.camera_zoom_speed * accel * dt
else:
    # Rotate pitch
    self.camera_pitch_vel += input_ud * self.camera_rotate_speed * accel * dt

# Forward/Backward: zoom
self.camera_distance_vel -= input_fb * self.camera_zoom_speed * accel * dt
```

### Velocity Integration

```python
# Apply damping
damping = self.camera_damping ** (dt * 60.0)
self.camera_yaw_vel *= damping
self.camera_pitch_vel *= damping
self.camera_distance_vel *= damping

# Update coordinates
self.camera_yaw += self.camera_yaw_vel * dt
self.camera_pitch += self.camera_pitch_vel * dt
self.camera_distance += self.camera_distance_vel * dt

# Clamp distance (optional pitch clamping removed for full 360°)
self.camera_distance = max(1.0, min(50.0, self.camera_distance))
```

## Integration Guide for New Scenes

### 1. Python Side (No Changes Needed!)

The camera system is already implemented in `preview_renderer.py`. Just use it as-is.

### 2. Shader Side (3 lines!)

Replace your manual camera setup with:

```glsl
// OLD (manual calculation):
vec3 cameraPos = vec3(x, y, z);
vec3 target = vec3(0, 0, 0);
vec3 forward = normalize(target - cameraPos);
vec3 right = normalize(cross(vec3(0, 1, 0), forward));
vec3 up = cross(forward, right);

// NEW (use precomputed):
vec3 cameraPos = iCameraPos;
vec3 right = iCameraRight;
vec3 up = iCameraUp;
vec3 forward = iCameraForward;
```

### 3. Test It

```bash
python examples/shader_preview.py --shader shaders/your_scene.glsl --width 512 --height 512
```

Use arrow keys to rotate - it will be perfectly smooth!

## Advantages Over Other Methods

### vs. Euler Angles (Roll/Pitch/Yaw)
- ✅ No gimbal lock
- ✅ No singularities at poles
- ✅ Simpler math

### vs. Quaternions
- ✅ More intuitive (yaw/pitch directly map to rotation)
- ✅ Simpler to understand and debug
- ✅ Natural for orbit-around-point behavior

### vs. Lookat + Cross Products
- ✅ No discontinuities when crossing poles
- ✅ No conditional logic for special cases
- ✅ More efficient (no normalize needed for up/right)

## Common Pitfalls to Avoid

❌ **Don't recompute orientation in shader** - Use the precomputed uniforms

❌ **Don't clamp pitch** - Allow full 360° rotation

❌ **Don't use world-up cross product** - Use tangent vectors instead

❌ **Don't normalize right/up** - They're already unit length

## Customization

### Change Rotation Speed
```python
self.camera_rotate_speed = 2.0  # Faster rotation
```

### Change Zoom Speed
```python
self.camera_zoom_speed = 10.0  # Faster zoom
```

### Change Initial Position
```python
self.camera_distance = 15.0   # Start farther away
self.camera_yaw = math.pi/4   # Start at 45°
self.camera_pitch = math.pi/6 # Start elevated
```

### Change Damping (Inertia)
```python
self.camera_damping = 0.95  # More glide
self.camera_damping = 0.8   # Less glide (more responsive)
```

## Game Controller Adaptation

When porting to Raspberry Pi with game controller:

```python
# Map analog stick to rotation
input_x = controller.left_stick_x  # -1 to 1
input_y = controller.left_stick_y  # -1 to 1

# Map triggers to zoom
input_zoom = controller.right_trigger - controller.left_trigger

# Apply same velocity physics
self.camera_yaw_vel += input_x * self.camera_rotate_speed * accel * dt
self.camera_pitch_vel += input_y * self.camera_rotate_speed * accel * dt
self.camera_distance_vel -= input_zoom * self.camera_zoom_speed * accel * dt
```

The shader code doesn't change at all!

## Performance Notes

- **CPU cost**: Negligible (a few trig operations per frame)
- **GPU cost**: Zero (orientation precomputed on CPU)
- **Memory**: 12 floats (3 vec3s) for orientation uniforms

## References

- Spherical coordinates: https://en.wikipedia.org/wiki/Spherical_coordinate_system
- Tangent space: https://en.wikipedia.org/wiki/Tangent_space
- Example shader: `shaders/navigate.glsl`
- Implementation: `src/piomatter/shader/preview_renderer.py`

---

**TL;DR**: Use spherical coordinate tangent vectors as camera basis. It's smooth everywhere and requires zero special cases!
