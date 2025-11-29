# Local Development Guide - LED Matrix Shaders on macOS

This guide explains how to develop and test LED matrix shaders on your MacBook before deploying to the Raspberry Pi.

## Overview

The `shader_preview.py` tool lets you preview shaders in a window on your Mac without needing the actual LED matrix hardware. This speeds up development significantly!

**Workflow:**
1. Develop/test shaders on Mac using `shader_preview.py`
2. Copy files to Raspberry Pi with `scp`
3. Run on actual LED matrix with `shader_demo.py`

## Setup on macOS

### 1. Install Python Dependencies

```bash
# Install pygame and PyOpenGL
pip install pygame PyOpenGL PyOpenGL_accelerate numpy

# Or if you use pip3:
pip3 install pygame PyOpenGL PyOpenGL_accelerate numpy
```

### 2. Get the Files

Copy these files from your Raspberry Pi to your Mac:

```bash
# From your Mac, copy the shader preview tool
scp brody@cube:~/Adafruit_Blinka_Raspberry_Pi5_Piomatter/shader_preview.py ~/led_dev/

# Also get the shader library
scp -r brody@cube:~/rpi-gpu-hub75-matrix/shaders ~/led_dev/shaders/
```

## Usage

### Basic Preview

Preview a shader at LED matrix resolution (64×64) scaled 8x for visibility:

```bash
cd ~/led_dev
python shader_preview.py shaders/cartoon.glsl --width 64 --height 64
```

This opens a 512×512 window (64×8) showing what the shader will look like on your LED matrix.

### All Options

```bash
python shader_preview.py <shader.glsl> [options]

Options:
  --width N       Shader width (LED matrix width, default: 64)
  --height N      Shader height (LED matrix height, default: 64)
  --scale N       Window scale factor (default: 8)
  --fps N         Target frame rate (default: 60)

Controls (while running):
  ESC or Q        Quit
  SPACE           Pause/Resume
  R               Restart (reset time to 0)
```

### Examples

**Standard 64×64 panel:**
```bash
python shader_preview.py shaders/flame.glsl --width 64 --height 64
```

**Larger 128×64 display:**
```bash
python shader_preview.py shaders/voronoi.glsl --width 128 --height 64 --scale 6
```

**Bigger window (10x scale):**
```bash
python shader_preview.py shaders/synthwave.glsl --width 64 --height 64 --scale 10
```

**Test at different resolutions:**
```bash
# Small 32×32
python shader_preview.py shaders/stars.glsl --width 32 --height 32 --scale 16

# Large 128×128
python shader_preview.py shaders/clouds.glsl --width 128 --height 128 --scale 4
```

## Development Workflow

### 1. Find Shaders to Test

Browse available shaders:

```bash
ls ~/led_dev/shaders/

# Quick test several shaders
for shader in ~/led_dev/shaders/{cartoon,flame,stars,voronoi}.glsl; do
    python shader_preview.py "$shader" --width 64 --height 64
done
```

### 2. Develop Your Own Shaders

Create a new shader file (Shadertoy format):

```glsl
// my_shader.glsl
// Simple animated gradient

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;

    // Time-based color animation
    vec3 col = 0.5 + 0.5 * cos(iTime + uv.xyx + vec3(0, 2, 4));

    fragColor = vec4(col, 1.0);
}
```

Test it:

```bash
python shader_preview.py my_shader.glsl --width 64 --height 64
```

### 3. Deploy to Raspberry Pi

Once your shader looks good, copy it to your Pi:

```bash
# Copy shader to Pi
scp my_shader.glsl brody@cube:~/shaders/

# SSH to Pi and run it
ssh brody@cube
cd ~/Adafruit_Blinka_Raspberry_Pi5_Piomatter
source env/bin/activate
python examples/shader_demo.py --shader ~/shaders/my_shader.glsl --width 64 --height 64
```

## Shader Compatibility Notes

The preview tool uses standard OpenGL (not OpenGL ES), so there are slight differences:

### ✅ Fully Compatible
- `uniform float iTime` - Elapsed time
- `uniform vec3 iResolution` - Display resolution
- `uniform int iFrame` - Frame counter
- `void mainImage(out vec4 fragColor, in vec2 fragCoord)` - Main function
- Most math and vector operations
- Standard GLSL functions (sin, cos, pow, mix, etc.)

### ⚠️ May Need Adjustment
- **Precision qualifiers** - Preview uses `#version 120` (desktop OpenGL), Pi uses `#version 310 es`
  - If a shader has precision issues on Mac, you may need to adjust
  - Generally shaders work fine without modification

### ❌ Not Yet Supported (in both preview and Pi)
- Texture inputs (`iChannel0`, `iChannel1`)
- Mouse input (`iMouse`)
- Multiple render passes (Buffer A, B, C)

## Tips for LED Matrix Shaders

### 1. Low Resolution Matters

LED matrices are typically 64×64 or smaller. Design shaders with this in mind:

**Good for low-res:**
- Bold geometric shapes
- High contrast patterns
- Large features
- Simple color gradients

**Avoid:**
- Fine details (will be lost)
- Thin lines (< 2 pixels)
- Complex textures
- Subtle gradients

### 2. Performance

The preview tool runs on your Mac's GPU and will perform differently than the Pi:

- **Mac**: May run 60+ FPS even on complex shaders
- **Pi 5**: Complex ray-marching shaders may run 20-40 FPS
- **Tip**: If a shader struggles on Mac, it will definitely struggle on Pi

### 3. Color and Brightness

LED matrices have different color characteristics than LCD screens:

- **Preview**: Shows accurate RGB colors
- **LED Matrix**: May have different color balance
- **Tip**: Test final result on actual hardware for color-critical work

## Recommended Shaders for LED Matrices

Based on the rpi-gpu-hub75-matrix shader library:

### Excellent for LED Displays
- `cartoon.glsl` - Bold shapes with edge detection
- `flame.glsl` - Fire simulation (great on LEDs!)
- `stars.glsl` - Starfield
- `synthwave.glsl` - Retro grid (iconic on LEDs)
- `lines.glsl` - Geometric patterns

### Good (Medium Complexity)
- `clouds.glsl` - Procedural clouds
- `voronoi.glsl` - Voronoi cells
- `water.glsl` - Water ripples
- `happy_jump.glsl` - Bouncing shapes

### Advanced (GPU Intensive)
- `mandle_brot.glsl` - Mandelbrot zoom
- `dragon_torus.glsl` - 3D torus
- `accretion.glsl` - Black hole
- `tentacles.glsl` - Ray-marched tentacles

## Troubleshooting

### "ModuleNotFoundError: No module named 'pygame'"

Install pygame:
```bash
pip install pygame PyOpenGL PyOpenGL_accelerate
```

### "Shader compilation failed"

The shader may use OpenGL ES features not available in desktop OpenGL. Check:
- Remove `precision mediump float;` declarations (not needed in #version 120)
- Check for ES-specific functions

### Window is too small/large

Adjust the scale:
```bash
# Bigger window
python shader_preview.py shader.glsl --width 64 --height 64 --scale 12

# Smaller window
python shader_preview.py shader.glsl --width 64 --height 64 --scale 4
```

### Poor performance on Mac

Some shaders are GPU-intensive:
- Reduce window size with `--scale 4`
- Try simpler shaders first
- Close other GPU-intensive apps

## File Organization

Recommended project structure:

```
~/led_dev/
├── shader_preview.py          # Preview tool (copy from Pi)
├── shaders/                    # Shader library
│   ├── cartoon.glsl
│   ├── flame.glsl
│   ├── ...
│   └── my_custom_shader.glsl  # Your shaders
└── notes.md                    # Development notes
```

## Sync Script

Create a sync script to easily copy files between Mac and Pi:

```bash
#!/bin/bash
# sync_to_pi.sh

PI="brody@cube"
PI_DIR="~/Adafruit_Blinka_Raspberry_Pi5_Piomatter"

echo "Syncing shaders to Pi..."
scp shaders/*.glsl $PI:~/shaders/

echo "Done! Run on Pi with:"
echo "  ssh $PI"
echo "  cd $PI_DIR && source env/bin/activate"
echo "  python examples/shader_demo.py --shader ~/shaders/your_shader.glsl"
```

Make it executable:
```bash
chmod +x sync_to_pi.sh
```

## Summary

**Develop on Mac:**
```bash
python shader_preview.py shaders/flame.glsl --width 64 --height 64
```

**Deploy to Pi:**
```bash
scp shaders/flame.glsl brody@cube:~/shaders/
ssh brody@cube
python examples/shader_demo.py --shader ~/shaders/flame.glsl
```

Happy shader development! 🎨✨
