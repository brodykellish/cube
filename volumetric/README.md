## Volumetric Cube Rendering

This directory contains tools for rendering 3D scenes volumetrically on a physical LED cube by rendering the scene from 6 different perspectives (one for each cube face).

### Concept

A physical LED cube has 6 faces, each displaying a 2D image. By rendering a 3D scene from 6 different camera positions (one per face, all looking toward the center), we create the illusion that the cube contains a 3D volumetric object.

```
         [top view]
              ↓
    [left] → ◉ ← [right]
              ↑
       [bottom view]

    [back view]  [front view]
```

Each face shows what the 3D object looks like from that perspective, creating a holographic/volumetric effect.

### Architecture

#### `VolumetricCubeRenderer`

Main class that handles the 6-perspective rendering:

```python
from volumetric.cube_renderer import VolumetricCubeRenderer

# Create renderer (64×64 per face)
cube = VolumetricCubeRenderer(face_size=64, face_distance=5.0)

# Load a volumetric shader
cube.load_shader("volumetric/shaders/sphere.glsl")

# Render all 6 faces
faces = cube.render_all_faces()
# Returns: {'front': pixels, 'back': pixels, 'left': pixels, ...}

# Render single face
front_pixels = cube.render_face('front')
```

**Key features:**
- Uses `ShaderRenderer` from the shader module
- One `StaticCamera` per face, positioned on each axis
- Single shader renders from all 6 perspectives
- Returns pixel arrays for LED matrix output or preview

#### `CubePreviewRenderer`

Preview tool for macOS development:

```python
from volumetric.cube_renderer import VolumetricCubeRenderer, CubePreviewRenderer

cube = VolumetricCubeRenderer(face_size=64)
cube.load_shader("volumetric/shaders/torus.glsl")

# Create preview with 4x scaling
preview = CubePreviewRenderer(cube, scale=4)

# Run interactive preview
preview.run(fps=30)
```

Displays all 6 faces in an unfolded cube pattern:

```
           [top]

[left] [front] [right] [back]

          [bottom]
```

### How It Works

#### 1. Camera Positioning

Each face has a camera positioned on one axis, looking toward the origin:

```python
FACE_CONFIGS = {
    'front':  position=(0, 0, +distance), look_at=(0, 0, 0)  # +Z
    'back':   position=(0, 0, -distance), look_at=(0, 0, 0)  # -Z
    'left':   position=(-distance, 0, 0), look_at=(0, 0, 0)  # -X
    'right':  position=(+distance, 0, 0), look_at=(0, 0, 0)  # +X
    'top':    position=(0, +distance, 0), look_at=(0, 0, 0)  # +Y
    'bottom': position=(0, -distance, 0), look_at=(0, 0, 0)  # -Y
}
```

All cameras use `StaticCamera` from the shader module - no movement, just fixed perspectives.

#### 2. Shader Requirements

Volumetric shaders should:
1. **Center content at origin** - All faces look toward (0, 0, 0)
2. **Use provided camera** - Respect `iCameraPos`, `iCameraRight`, `iCameraUp`, `iCameraForward`
3. **Work from any angle** - Scene should look interesting from all 6 perspectives
4. **Use raymarching** - SDF-based rendering works best for volumetric effects

#### 3. Rendering Pipeline

```python
# For each face:
for face in ['front', 'back', 'left', 'right', 'top', 'bottom']:
    1. Set camera to face's position
    2. Render shader from that perspective
    3. Read back pixels (64×64×3 array)
    4. Send to LED matrix or display in preview
```

### Creating Volumetric Shaders

#### Template Structure

```glsl
// 1. Define your scene SDF
float sceneSDF(vec3 p) {
    // Your 3D object centered at origin
    return sdSphere(p, 1.5);  // Example: sphere
}

// 2. Calculate normals
vec3 calcNormal(vec3 p) {
    float eps = 0.001;
    // Standard normal calculation
}

// 3. Raymarch from camera
float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);
        if (d < 0.001) return t;
        if (t > maxDist) break;
        t += d;
    }
    return -1.0;
}

// 4. Main image function
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized coords
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use renderer's camera (critical!)
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // Raymarch and shade
    float t = raymarch(ro, rd, 20.0);
    vec3 color = // ... lighting calculation
    fragColor = vec4(color, 1.0);
}
```

**Key requirements:**
- **Must use `iCameraPos`, `iCameraRight`, `iCameraUp`, `iCameraForward`** - Don't hardcode camera!
- Center your scene at origin
- Keep objects within ~3 units of origin for best visibility
- Use distance fog to fade far objects

#### Example Shaders

**`sphere.glsl`** - Simple pulsing sphere with rotating light
- Good starting point
- Single SDF primitive
- Basic Phong lighting

**`torus.glsl`** - Rotating torus with rainbow colors
- More complex geometry
- Multiple rotating lights
- Rim lighting and specular highlights

### Usage Examples

#### Preview Mode (Development)

```python
from volumetric.cube_renderer import VolumetricCubeRenderer, CubePreviewRenderer

# Create cube renderer
cube = VolumetricCubeRenderer(face_size=64, face_distance=5.0)

# Load shader
cube.load_shader("volumetric/shaders/torus.glsl")

# Create and run preview
preview = CubePreviewRenderer(cube, scale=4)
preview.run(fps=30)  # Interactive window
```

#### LED Matrix Mode (Production)

```python
from volumetric.cube_renderer import VolumetricCubeRenderer

# Initialize your LED matrices (6 of them, one per face)
matrices = {
    'front': FrontLEDMatrix(),
    'back': BackLEDMatrix(),
    # ... etc
}

# Create renderer
cube = VolumetricCubeRenderer(face_size=64)
cube.load_shader("volumetric/shaders/sphere.glsl")

# Render loop
while True:
    # Get all 6 face pixel arrays
    faces = cube.render_all_faces()

    # Send each face to its LED matrix
    for name, pixels in faces.items():
        matrices[name].show(pixels)
```

#### Single Face Testing

```python
# Test just one face
cube = VolumetricCubeRenderer(face_size=64)
cube.load_shader("volumetric/shaders/sphere.glsl")

# Render only front face
front_pixels = cube.render_face('front')

# Display or save for debugging
from PIL import Image
img = Image.fromarray(front_pixels, 'RGB')
img.save('front_face.png')
```

### Performance Considerations

#### Rendering Speed

Each face is rendered independently:
- 6 faces × 64×64 pixels = 24,576 pixels total
- With raymarching, each pixel traces 64-80 steps
- Total: ~1.5-2 million ray steps per frame

**Optimization tips:**
1. **Reduce face_size** - 32×32 is still effective
2. **Limit raymarch iterations** - 48 steps often sufficient
3. **Simple SDFs** - Sphere/torus faster than complex CSG
4. **Offscreen rendering** - Use `windowed=False` on Pi

#### Memory Usage

- Per face: 64×64×3 bytes = 12 KB
- All 6 faces: 72 KB
- Plus renderer overhead: ~100 KB total

Very manageable even on Raspberry Pi.

### Design Patterns

#### Pattern 1: Static Scene

Scene doesn't change, just rotates view:

```glsl
float sceneSDF(vec3 p) {
    // Rotate the point, not the camera
    vec3 rotated = rotate(p, iTime);
    return sdYourObject(rotated);
}
```

#### Pattern 2: Animated Scene

Scene elements move/pulse/deform:

```glsl
float sceneSDF(vec3 p) {
    float pulse = sin(iTime * 2.0) * 0.5;
    return sdSphere(p, 1.5 + pulse);
}
```

#### Pattern 3: Multi-Object

Multiple objects with different behaviors:

```glsl
float sceneSDF(vec3 p) {
    float sphere = sdSphere(p - vec3(0, 0, 0), 1.0);
    float box = sdBox(p - vec3(sin(iTime) * 2.0, 0, 0), vec3(0.5));

    // Union
    return min(sphere, box);
}
```

#### Pattern 4: Audio Reactive

Use audio input to drive visuals:

```glsl
float sceneSDF(vec3 p) {
    // Scale with beat pulse
    float scale = 1.0 + iBeatPulse * 0.5;
    return sdSphere(p / scale, 1.5) * scale;
}
```

### Integration with LED Cube Hardware

#### Face Mapping

Map renderer faces to physical cube faces:

```python
# Physical cube face indices (your hardware)
HARDWARE_MAPPING = {
    'front': 0,   # Panel 0
    'right': 1,   # Panel 1
    'back': 2,    # Panel 2
    'left': 3,    # Panel 3
    'top': 4,     # Panel 4
    'bottom': 5,  # Panel 5
}

# Render and map
faces = cube.render_all_faces()
for name, pixels in faces.items():
    panel_index = HARDWARE_MAPPING[name]
    hardware.send_to_panel(panel_index, pixels)
```

#### Orientation Correction

If your physical cube has rotated panels:

```python
import numpy as np

def rotate_face(pixels, angle):
    """Rotate pixel array 90/180/270 degrees."""
    k = angle // 90  # Number of 90° rotations
    return np.rot90(pixels, k)

# Apply corrections
faces['top'] = rotate_face(faces['top'], 90)
faces['bottom'] = rotate_face(faces['bottom'], -90)
```

### Extending the System

#### Add New Input Sources

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import AudioFileInput

cube = VolumetricCubeRenderer(face_size=64)

# Add audio reactivity to all faces
audio = AudioFileInput("music.mp3", bpm=120)
cube.renderer.add_input_source(audio)

cube.load_shader("volumetric/shaders/audio_reactive.glsl")
```

The shader can then use `iBPM`, `iBeatPhase`, `iBeatPulse` uniforms.

#### Custom Face Distances

Different perspectives for artistic effects:

```python
# Closer view (more dramatic)
cube = VolumetricCubeRenderer(face_size=64, face_distance=3.0)

# Farther view (more orthographic)
cube = VolumetricCubeRenderer(face_size=64, face_distance=10.0)
```

#### Multiple Objects

Create a scene with multiple volumetric elements:

```glsl
float sceneSDF(vec3 p) {
    // Planet
    float planet = sdSphere(p, 2.0);

    // Orbiting moons
    vec3 moon1Pos = vec3(cos(iTime) * 4.0, 0, sin(iTime) * 4.0);
    float moon1 = sdSphere(p - moon1Pos, 0.5);

    vec3 moon2Pos = vec3(cos(iTime + 3.14) * 4.0, 0, sin(iTime + 3.14) * 4.0);
    float moon2 = sdSphere(p - moon2Pos, 0.5);

    return min(planet, min(moon1, moon2));
}
```

### Troubleshooting

#### Problem: Black screens on some faces

**Solution:** Check camera vectors are being used:
```glsl
// Wrong - hardcoded camera
vec3 ro = vec3(0, 0, 5);

// Correct - use provided camera
vec3 ro = iCameraPos;
```

#### Problem: Scene looks stretched or distorted

**Solution:** Ensure aspect-correct ray direction:
```glsl
// Wrong
vec2 uv = fragCoord / iResolution.xy;

// Correct - maintains aspect ratio
vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
```

#### Problem: Low frame rate

**Solution:**
1. Reduce face_size: `VolumetricCubeRenderer(face_size=32)`
2. Reduce raymarch iterations: `for (int i = 0; i < 48; i++)`
3. Use simpler SDFs
4. Increase step size: `t += d * 0.9;` (less accurate but faster)

#### Problem: Objects not centered in all views

**Solution:** Scene must be centered at origin (0, 0, 0). Check your SDF definitions.

### Future Enhancements

Possible extensions to the system:

1. **Stereo 3D**: Render left/right eye views for each face
2. **Motion blur**: Temporal antialiasing across frames
3. **Cached face rendering**: Only update changed faces
4. **Adaptive quality**: Reduce quality on complex faces
5. **Face prioritization**: Update front face more frequently
6. **GPU compute shaders**: Parallel rendering of all 6 faces

### See Also

- `src/adafruit_blinka_raspberry_pi5_piomatter/shader/` - Shader module
- `docs/INPUT_ABSTRACTION.md` - Input system documentation
- `docs/CAMERA_MODES.md` - Camera mode documentation
- Shadertoy.com - Inspiration for volumetric shaders

### Quick Start

```bash
# Install dependencies (if needed)
pip install pygame PyOpenGL PyOpenGL_accelerate numpy pillow

# Run sphere example
python volumetric/cube_renderer.py

# Or directly:
cd volumetric
python -c "from cube_renderer import main; main()"
```

Press ESC or Q to quit the preview.
