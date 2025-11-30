# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Library Overview

`Adafruit_Blinka_Raspberry_Pi5_Piomatter` is a Python library for driving HUB75 RGB LED matrix panels on Raspberry Pi 5 using the RP1 PIO (Programmable I/O) hardware. It provides a clean, numpy-based API for rapid prototyping and Python-based LED matrix applications.

## Key Features

- **Python API**: Clean interface with numpy integration
- **PIO-Based**: Uses RP1 PIO hardware for precise timing (not GPIO bit-banging)
- **Runtime Configuration**: Switch pinouts and geometries without recompilation
- **Multiple Colorspaces**: RGB565, RGB888Packed formats
- **Flexible Geometry**: Serpentine layouts, rotations, custom pixel mappings
- **Good Examples**: Framebuffer mirroring, GIF playback, virtual X display, terminal rendering
- **GLSL Shader Support**: Real-time shader rendering with keyboard navigation

## Shader Development

The project includes a shader preview tool for testing GLSL shaders without hardware.

### Shader Preview Tool

**IMPORTANT**: Always use `--scale 1` or omit the scale parameter entirely. Higher scale values can cause issues.

**Correct usage:**
```bash
# Preferred (default scale=1)
python examples/shader_preview.py --shader shaders/flame.glsl --width 64 --height 64

# Explicit scale=1 (same as above)
python examples/shader_preview.py --shader shaders/flame.glsl --width 64 --height 64 --scale 1
```

**Avoid:**
```bash
# DO NOT USE: scale values > 1 can cause problems
python examples/shader_preview.py --shader shaders/flame.glsl --width 64 --height 64 --scale 8
```

**Shader Preview Controls:**
- **ESC or Q**: Quit
- **R**: Reload current shader (useful during development)
- **B**: Browse and switch between shaders
- **Arrow Keys/WASD**: Rotate camera around origin
- **Shift+Up/Down** or **E/C**: Zoom in/out

**GLSL 1.20 Compatibility:**
All shaders must be compatible with GLSL 1.20 (OpenGL 2.1). The renderer provides compatibility functions:
- `tanh()` - Hyperbolic tangent (vec2, vec3, vec4, float)
- `round()` - Rounding function (vec2, vec3, vec4, float)
- `texture2D()` - Use instead of `texture()`
- `bitShiftRight()`, `bitAnd()` - Bit operation emulation

**Hybrid Input System:**
Shaders have access to both raw input and precomputed camera vectors:

```glsl
// Raw input (game controller friendly)
uniform vec4 iInput;  // (left/right, up/down, forward/backward, unused)

// Precomputed camera (convenience)
uniform vec3 iCameraPos;
uniform vec3 iCameraRight;
uniform vec3 iCameraUp;
uniform vec3 iCameraForward;

// Audio reactive (optional)
uniform float iBPM;        // Beats per minute
uniform float iBeatPhase;  // 0-1 position in beat cycle
uniform float iBeatPulse;  // 1.0 on beat, decays to 0
```

Most shaders should use precomputed camera:
```glsl
vec3 ro = iCameraPos;
vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
```

For custom input handling or game-like effects, use `iInput` directly.

See `docs/SHADER_INPUT.md` for detailed usage patterns and examples.

## Installation

### From Source (Development)

```bash
cd ~/Adafruit_Blinka_Raspberry_Pi5_Piomatter

# Create virtual environment (optional but recommended)
python3 -m venv env
source env/bin/activate

# Install in development mode
pip install -e .
```

### From PyPI (Production)

```bash
pip install Adafruit-Blinka-Raspberry-Pi5-Piomatter
```

### System Requirements

**PIO Device Permissions**:
```bash
# Check PIO device exists
ls -l /dev/pio0

# If owned by root, add udev rule
echo 'SUBSYSTEM=="*-pio", GROUP="gpio", MODE="0660"' | sudo tee /etc/udev/rules.d/99-com.rules

# Add user to gpio group
sudo usermod -aG gpio $USER

# Reboot for changes to take effect
```

**Dependencies**:
- Python 3.9+
- NumPy
- Pillow (for image examples)
- click (for CLI examples)

## Architecture

### Core Components

**C++ Backend** (`src/`):
- `pymain.cpp`: Python bindings using pybind11
- `protomatter.pio`: PIO assembly program for HUB75 protocol
- `protodemo.cpp`: Demo/test application
- `piolib/`: PIO abstraction layer
  - `pio_rp1.c`: RP1-specific PIO implementation for Pi 5
  - `piolib.c`: Generic PIO interface

**Python Frontend** (`src/piomatter/`):
- `__init__.py`: Main module exposing PioMatter, Geometry, Pinout, etc.
- `click.py`: Command-line argument helpers (`@piomatter_click.standard_options`)
- `pixelmappers.py`: Custom pixel mapping functions

**Examples** (`examples/`):
- `simpletest.py`: Basic colored rectangles
- `fbmirror.py`: Mirror Linux framebuffer to matrix
- `virtualdisplay.py`: Run X applications on matrix
- `play_gif.py`: Animated GIF player
- `rainbow_spiral.py`: Procedural animation

### Build System

The library uses `setup.py` with native extension compilation:

```bash
# Build in-place (for development)
python setup.py build_ext --inplace

# Install
python setup.py install

# Or use pip (recommended)
pip install .
```

**Build Dependencies**:
- C++11 compiler (g++)
- Python development headers (`python3-dev`)
- pybind11 (automatically fetched)

## Python API

### Core Classes

#### `PioMatter` - The Display Driver

Main class for controlling the LED matrix:

```python
matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,  # or RGB565
    pinout=piomatter.Pinout.AdafruitMatrixBonnet,   # Hardware configuration
    framebuffer=numpy_array,                        # Your drawing buffer
    geometry=geometry_object                         # Panel layout
)

# Update display
matrix.show()
```

**Key Methods**:
- `show()`: Push framebuffer to display (blocking until complete)
- Properties: `width`, `height` (read-only)

#### `Geometry` - Panel Configuration

Defines the physical layout and color depth:

```python
geometry = piomatter.Geometry(
    width=64,                    # Total width in pixels
    height=32,                   # Total height in pixels
    n_planes=10,                 # Color depth (4-11 recommended)
    n_addr_lines=4,              # Address lines (4 for 1:16 scan, 5 for 1:32)
    n_temporal_planes=0,         # Temporal dithering (0, 2, or 4)
    rotation=piomatter.Orientation.Normal,  # Rotation/orientation
    serpentine=True,             # Panel chaining pattern
    n_lanes=2,                   # Lanes per connector (usually 2)
    map=None                     # Optional: custom pixel mapping function
)
```

**Parameters Explained**:

- **`n_planes`** (4-11): Color depth in bit-planes
  - 4 planes = 4 bits per color = 4096 colors
  - 10 planes = 10 bits per color = ~1 billion colors
  - Lower values = higher refresh rate, less color depth
  - Higher values = more colors, may shimmer on some panels

- **`n_addr_lines`** (4 or 5): Determines scan rate
  - 4 lines = 1:16 scan (32-pixel tall panels)
  - 5 lines = 1:32 scan (64-pixel tall panels)

- **`n_temporal_planes`** (0, 2, or 4): Temporal dithering
  - 0 or 1 = disabled
  - 2, 4 = enable temporal dithering (improves perceived color, may cause shimmer)

- **`serpentine`**: Panel chaining layout
  - `True`: Panels alternate direction (common for multiple panels)
  - `False`: All panels same direction

- **`rotation`**: Display orientation
  - `Orientation.Normal`: No rotation
  - `Orientation.Rotate90`: 90° clockwise
  - `Orientation.Rotate180`: 180°
  - `Orientation.Rotate270`: 270° clockwise

#### `Pinout` - Hardware Configuration

Predefined pinout configurations:

```python
piomatter.Pinout.AdafruitMatrixBonnet       # Adafruit Matrix Bonnet
piomatter.Pinout.AdafruitMatrixHatRGB       # Adafruit HAT (RGB order)
piomatter.Pinout.AdafruitMatrixHatBGR       # Adafruit HAT (BGR order)
```

**Custom Pinout**: Can define custom pin mappings (requires C++ binding extension).

#### `Colorspace` - Pixel Format

Framebuffer pixel formats:

```python
piomatter.Colorspace.RGB565        # 16-bit: 5 red, 6 green, 5 blue
piomatter.Colorspace.RGB888Packed  # 24-bit: 8 red, 8 green, 8 blue
```

**Choosing Colorspace**:
- `RGB565`: Lower memory, faster updates, good for simple graphics
- `RGB888Packed`: Full color, best quality, higher memory usage

### Basic Usage Pattern

```python
import numpy as np
import piomatter as piomatter

# 1. Define geometry
geometry = piomatter.Geometry(
    width=64, height=32, n_planes=10, n_addr_lines=4
)

# 2. Create framebuffer (numpy array)
# For RGB888Packed: shape = (height, width, 3), dtype=uint8
framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)

# 3. Initialize display
matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=piomatter.Pinout.AdafruitMatrixBonnet,
    framebuffer=framebuffer,
    geometry=geometry
)

# 4. Draw and display
while True:
    # Modify framebuffer using numpy operations
    framebuffer[10:20, 10:20] = [255, 0, 0]  # Red rectangle

    # Push to display
    matrix.show()
```

### Advanced: Custom Pixel Mapping

For non-standard panel arrangements (e.g., multiple panels in custom layout):

```python
from piomatter.pixelmappers import simple_multilane_mapper

# Create custom mapping
pixelmap = simple_multilane_mapper(
    width=128, height=64,
    n_addr_lines=5,
    n_lanes=4  # 4 lanes = 2 connectors
)

# Use in geometry
geometry = piomatter.Geometry(
    width=128, height=64,
    n_planes=10, n_addr_lines=5,
    n_lanes=4,
    map=pixelmap  # Custom mapping
)
```

**When to use custom mapping**:
- More than 2 lanes (multiple connectors)
- Non-standard panel chaining
- Panels in irregular arrangements

## Command-Line Helpers

The `click.py` module provides decorators for consistent CLI:

```python
import click
import piomatter.click as piomatter_click

@click.command
@piomatter_click.standard_options  # Adds all standard flags
def my_program(width, height, serpentine, rotation, pinout,
               n_planes, n_temporal_planes, n_addr_lines, n_lanes):
    # Your code here
    pass
```

**Standard Options Added**:
- `--width`: Panel width (default 64)
- `--height`: Panel height (default 32)
- `--serpentine / --no-serpentine`: Panel chaining
- `--orientation`: Rotation (Normal, Rotate90, Rotate180, Rotate270)
- `--pinout`: Hardware pinout
- `--num-planes`: Color depth
- `--num-temporal-planes`: Temporal dithering
- `--num-address-lines`: Scan rate (4 or 5)
- `--num-lanes`: Lanes per connector

**Example Command**:
```bash
python my_program.py --width 128 --height 64 --pinout AdafruitMatrixHatRGB \
    --num-planes 10 --num-address-lines 5
```

## Example Code Patterns

### Simple Rectangle Drawing

```python
import numpy as np
import piomatter as piomatter

geometry = piomatter.Geometry(width=64, height=32, n_planes=10, n_addr_lines=4)
framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)
matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=piomatter.Pinout.AdafruitMatrixBonnet,
    framebuffer=framebuffer,
    geometry=geometry
)

# Draw colored rectangles
framebuffer[0:10, 0:20] = [255, 0, 0]    # Red
framebuffer[10:20, 0:20] = [0, 255, 0]   # Green
framebuffer[20:30, 0:20] = [0, 0, 255]   # Blue

matrix.show()
```

### Animation Loop

```python
import time

for frame in range(1000):
    # Clear screen
    framebuffer[:, :] = 0

    # Draw moving pixel
    x = frame % geometry.width
    y = frame // geometry.width % geometry.height
    framebuffer[y, x] = [255, 255, 255]

    matrix.show()
    time.sleep(0.01)
```

### Image Display

```python
from PIL import Image

# Load image
img = Image.open('myimage.png')
img = img.resize((geometry.width, geometry.height))
img = img.convert('RGB')

# Convert to numpy and display
framebuffer[:, :] = np.array(img)
matrix.show()
```

### GIF Animation

```python
from PIL import Image

# Load GIF
gif = Image.open('animation.gif')

try:
    while True:
        for frame_num in range(gif.n_frames):
            gif.seek(frame_num)
            frame = gif.convert('RGB').resize((geometry.width, geometry.height))
            framebuffer[:, :] = np.array(frame)
            matrix.show()
            time.sleep(1.0 / gif.info.get('duration', 100) * 1000)
except KeyboardInterrupt:
    pass
```

### Framebuffer Mirroring

See `examples/fbmirror.py` for complete example:

```python
# Map Linux framebuffer
linux_fb = np.memmap('/dev/fb0', mode='r',
                     shape=(screen_height, stride // bytes_per_pixel),
                     dtype=np.uint16)

# Copy region to matrix
while True:
    framebuffer[:, :] = linux_fb[yoffset:yoffset+height, xoffset:xoffset+width]
    matrix.show()
```

## Performance Optimization

### Frame Rate Considerations

**Factors affecting refresh rate**:
1. **Number of planes** (`n_planes`): More planes = lower refresh rate
2. **Panel size**: Larger panels take longer to scan
3. **Temporal planes**: Adds overhead but may improve perceived quality

**Typical refresh rates**:
- 64×32 panel, 10 planes: ~200-400 Hz
- 128×64 panel, 10 planes: ~100-200 Hz

**Optimization tips**:
- Reduce `n_planes` if colors look good enough (7-8 often sufficient)
- Use `n_temporal_planes=2` for better color without adding bit-planes
- Use RGB565 instead of RGB888Packed for faster updates
- Minimize Python overhead between `show()` calls

### Memory Efficiency

**Framebuffer sizes**:
- RGB565: `width × height × 2` bytes
- RGB888Packed: `width × height × 3` bytes

Example: 64×32 panel
- RGB565: 4 KB
- RGB888Packed: 6 KB

For memory-constrained applications, use RGB565.

### NumPy Optimization

Use vectorized operations instead of loops:

```python
# Bad (slow)
for y in range(height):
    for x in range(width):
        framebuffer[y, x] = compute_pixel(x, y)

# Good (fast)
x_coords, y_coords = np.meshgrid(np.arange(width), np.arange(height))
framebuffer[:, :] = compute_pixel_vectorized(x_coords, y_coords)
```

## Common Issues & Troubleshooting

### Permission Denied: /dev/pio0

**Symptom**: `PermissionError: [Errno 13] Permission denied: '/dev/pio0'`

**Solutions**:
1. Add udev rule: `echo 'SUBSYSTEM=="*-pio", GROUP="gpio", MODE="0660"' | sudo tee /etc/udev/rules.d/99-com.rules`
2. Add user to gpio group: `sudo usermod -aG gpio $USER`
3. Reboot or reload udev: `sudo udevadm control --reload-rules && sudo udevadm trigger`

### Wrong Colors / Color Order

**Symptom**: Colors appear wrong (e.g., red shows as blue)

**Solutions**:
- Try different pinout: `AdafruitMatrixHatRGB` vs `AdafruitMatrixHatBGR`
- Some panels have reversed color order
- Check physical wiring matches expected pinout

### Flickering / Shimmer

**Symptom**: Display flickers or shimmers, especially with temporal planes

**Solutions**:
- Reduce or disable temporal planes: `n_temporal_planes=0`
- Increase `n_planes` (more color depth = less dithering needed)
- Check power supply (insufficient current can cause flickering)

### Display Not Working

**Checklist**:
1. `/dev/pio0` exists and is accessible
2. Correct pinout selected for hardware
3. Correct number of address lines (4 for 32-pixel tall, 5 for 64-pixel tall)
4. Power supply adequate (5V, 2-4A per 64×32 panel at full brightness)
5. Proper ground connection between Pi and panel power supply

### Performance Issues

**Symptom**: Slow updates, low frame rate

**Solutions**:
- Reduce `n_planes` (10 → 8 or 7)
- Use RGB565 instead of RGB888Packed
- Profile Python code (avoid tight loops, use NumPy vectorization)
- Consider switching to rpi-gpu-hub75-matrix for GPU acceleration

## Development Workflow

### Modifying C++ Code

After changing C++ sources (`src/*.cpp`, `src/*.c`):

```bash
# Rebuild extension
pip install -e . --force-reinstall --no-deps

# Or manually
python setup.py build_ext --inplace
```

### Testing Changes

```bash
# Run simple test
python examples/simpletest.py --width 64 --height 32

# Run with different pinout
python examples/simpletest.py --pinout AdafruitMatrixHatBGR
```

### Adding New Examples

1. Create new Python file in `examples/`
2. Use `@piomatter_click.standard_options` decorator for CLI consistency
3. Follow existing example patterns (see `simpletest.py`)

## Integration with Other Libraries

### Pillow (PIL)

For image processing:

```python
from PIL import Image, ImageDraw, ImageFont

# Create image
img = Image.new('RGB', (geometry.width, geometry.height))
draw = ImageDraw.Draw(img)

# Draw text
font = ImageFont.truetype('font.ttf', 12)
draw.text((5, 5), "Hello!", font=font, fill=(255, 255, 255))

# Display
framebuffer[:, :] = np.array(img)
matrix.show()
```

### OpenCV

For video processing:

```python
import cv2

cap = cv2.VideoCapture('video.mp4')

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Resize and convert BGR → RGB
    frame = cv2.resize(frame, (geometry.width, geometry.height))
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    framebuffer[:, :] = frame
    matrix.show()
```

### Matplotlib

For plotting on matrix:

```python
import matplotlib.pyplot as plt
import io

fig, ax = plt.subplots(figsize=(geometry.width/10, geometry.height/10))
ax.plot([0, 1, 2, 3], [0, 1, 4, 9])

# Render to buffer
buf = io.BytesIO()
fig.savefig(buf, format='png', dpi=10)
buf.seek(0)

# Load and display
img = Image.open(buf).convert('RGB')
framebuffer[:, :] = np.array(img)
matrix.show()
```

## Extending the Library

### Custom Pixel Mappers

Create custom pixel mapping function:

```python
def my_custom_mapper(width, height, n_addr_lines):
    """Returns a numpy array of shape (height, width) with physical addresses."""
    mapping = np.zeros((height, width), dtype=np.int32)

    # Your custom mapping logic
    for y in range(height):
        for x in range(width):
            # Calculate physical pixel address
            mapping[y, x] = compute_address(x, y)

    return mapping

# Use in geometry
geometry = piomatter.Geometry(
    width=width, height=height,
    n_planes=10, n_addr_lines=5,
    map=my_custom_mapper(width, height, 5)
)
```

### Adding C++ Features

1. Edit `src/pymain.cpp` to add new bindings
2. Follow pybind11 patterns for exposing C++ to Python
3. Rebuild with `pip install -e .`

Example:
```cpp
m.def("my_new_function", &my_new_function, "Documentation");
```

## Comparison with rpi-gpu-hub75-matrix

| Feature | Adafruit (this library) | rpi-gpu-hub75-matrix |
|---------|------------------------|----------------------|
| Language | Python | C |
| API | NumPy-based, intuitive | Function calls, struct-based |
| Shader support | No | Yes (GLSL) |
| Video playback | Via OpenCV/Pillow | Built-in (FFmpeg) |
| Refresh rate | Good (~200-400 Hz) | Excellent (9600 Hz base) |
| Color processing | Basic | Advanced (tone mapping, gamma, dither) |
| Setup complexity | Low (pip install) | Medium (compile, install) |
| Flexibility | High (runtime config) | Medium (compile-time pinout) |
| Best for | Prototyping, Python apps | Performance, shaders, video |

**When to use this library**:
- Python-based projects
- Rapid prototyping
- Integration with Python ecosystem (NumPy, Pillow, etc.)
- Need runtime configuration changes

**When to use rpi-gpu-hub75-matrix**:
- Need GPU shader support
- Highest refresh rates
- Advanced color processing
- Video playback performance critical
