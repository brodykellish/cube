# Audio Spectrum Visualizer

A 3D audio-reactive shader system that visualizes audio frequency spectrum as a radial topographic heightmap.

## Features

- **FFT-based audio analysis** - Real-time frequency spectrum extraction
- **Radial visualization** - Frequency bins mapped to radius, amplitude to height
- **Procedural distortion** - Noise-based effects for dynamic appearance
- **Multiple input formats** - Supports `.mp4`, `.mp3`, `.wav`, `.ogg`, `.flac`
- **Synchronized playback** - Audio plays while shader renders
- **Interactive camera** - Navigate around the visualization using keyboard

## Quick Start

### Installation

Install required dependencies:

```bash
pip install moviepy librosa pygame numpy
```

### Basic Usage

Run the audio spectrum visualizer with an audio/video file:

```bash
python examples/shader_preview.py shaders/audio_spectrum.glsl \
    --audio path/to/your/audio.mp4 \
    --width 512 --height 512 --scale 1
```

### Example with Sample Audio

```bash
# With a video file
python examples/shader_preview.py shaders/audio_spectrum.glsl \
    --audio ~/Videos/music_video.mp4 \
    --width 512 --height 512

# With an audio file
python examples/shader_preview.py shaders/audio_spectrum.glsl \
    --audio ~/Music/song.mp3 \
    --width 512 --height 512
```

## How It Works

### 1. Audio Processing (`audio_processor.py`)

The `AudioProcessor` class handles:

- **Loading audio** from video (moviepy) or audio files (librosa)
- **FFT analysis** with configurable window size (default: 512 samples)
- **Temporal smoothing** to reduce jitter
- **Texture formatting** for OpenGL shader input

```python
# Inside AudioProcessor
def update(self) -> np.ndarray:
    # Extract audio window at current playback position
    window = audio_data[sample_pos:sample_pos + fft_size]

    # Apply Hann window
    window = window * np.hanning(fft_size)

    # Compute FFT
    fft = np.fft.rfft(window)
    magnitude = np.abs(fft)

    # Normalize and smooth
    magnitude = magnitude / (fft_size / 2)
    smoothed_spectrum = smooth_factor * prev + (1 - smooth_factor) * magnitude

    return smoothed_spectrum
```

### 2. Shader Visualization (`audio_spectrum.glsl`)

The shader renders a 3D radial heightmap:

**Frequency Mapping:**
```glsl
// Convert 3D position to cylindrical coordinates
float radius = length(p.xz);
float freq = clamp(radius / 10.0, 0.0, 0.99);

// Sample audio spectrum at this frequency
float amplitude = texture(iChannel0, vec2(freq, 0.5)).r;
```

**Height Calculation:**
```glsl
// Base height from audio amplitude
float height = amplitude * 3.0;

// Add procedural noise for visual interest
vec2 noiseCoord = vec2(freq * 20.0, angle * 3.0 + iTime * 0.5);
height += noise(noiseCoord) * 0.3;
height += noise(noiseCoord * 3.0) * 0.1;

// Distance to surface
return p.y - height;
```

**Coloring:**
```glsl
// Frequency-based color gradient
vec3 baseColor = vec3(
    1.0 - freq,           // Red for low frequencies (bass)
    sin(freq * 3.14159),  // Green for mid frequencies
    freq                  // Blue for high frequencies (treble)
);

// Modulate by amplitude
baseColor *= (0.5 + amplitude * 1.5);
```

## Architecture

```
Audio File (.mp4, .mp3, .wav)
         |
         v
   AudioProcessor
    - Load audio
    - Perform FFT
    - Smooth spectrum
         |
         v
  OpenGL Texture (1×512 RGB)
    - R channel: amplitude
    - Updated each frame
         |
         v
   Shader (iChannel0)
    - Sample spectrum
    - Raymarch heightmap
    - Render colors
         |
         v
   Preview Window
```

## Customization

### Adjust FFT Resolution

Modify `fft_size` in `audio_processor.py`:

```python
# More frequency bins (smoother but more expensive)
AudioProcessor(audio_file, fft_size=1024)

# Fewer bins (faster but coarser)
AudioProcessor(audio_file, fft_size=256)
```

### Change Visualization Scale

In `audio_spectrum.glsl`, adjust the radius mapping:

```glsl
// Larger visualization (spread out)
float freq = clamp(radius / 20.0, 0.0, 0.99);

// Smaller visualization (more compact)
float freq = clamp(radius / 5.0, 0.0, 0.99);
```

### Adjust Height Multiplier

```glsl
// More dramatic height changes
float height = amplitude * 6.0;

// Subtle height changes
float height = amplitude * 1.5;
```

### Modify Noise Amount

```glsl
// More chaotic distortion
float noiseVal = noise(noiseCoord) * 0.6;
noiseVal += noise(noiseCoord * 3.0) * 0.3;

// Cleaner, less distortion
float noiseVal = noise(noiseCoord) * 0.1;
noiseVal += noise(noiseCoord * 3.0) * 0.05;
```

## Controls

The visualizer uses the spherical camera system for smooth navigation:

| Keys | Action |
|------|--------|
| **Left/Right** (A/D) | Rotate horizontally around visualization |
| **Up/Down** (W/S) | Rotate vertically around visualization |
| **Shift+Up/Down** | Zoom in/out |
| **PageUp/PageDown** (E/C) | Zoom in/out |
| **R** | Restart shader (reset time) |
| **ESC or Q** | Quit |

See [SPHERICAL_CAMERA.md](SPHERICAL_CAMERA.md) for details on the camera system.

## Command-Line Options

```bash
python examples/shader_preview.py shaders/audio_spectrum.glsl \
    --audio FILE           # Path to audio/video file (required for audio shaders)
    --width W              # Display width (default: 64)
    --height H             # Display height (default: 64)
    --scale S              # Window scale factor (default: 1)
    --fps FPS              # Target frame rate (default: 60)
```

## Troubleshooting

### Audio Not Playing

**Symptom**: Visualization shows but no audio plays

**Solution**: Audio playback requires `pygame.mixer`. If it fails, visualization continues without sound. Check for error messages at startup.

### No Visualization Movement

**Symptom**: Heightmap is flat or static

**Solutions**:
1. Ensure `--audio` flag is provided
2. Check audio file path is correct
3. Verify audio file format is supported (`.mp4`, `.mp3`, `.wav`)
4. Install dependencies: `pip install moviepy librosa`

### Import Errors

**Symptom**: `ImportError: No module named 'moviepy'` or `'librosa'`

**Solution**:
```bash
# For video files
pip install moviepy

# For audio files
pip install librosa

# Both (recommended)
pip install moviepy librosa
```

### Choppy Visualization

**Symptom**: Visualization stutters or freezes

**Solutions**:
- Reduce FFT size: Use `--fft-size 256` (requires code modification)
- Lower resolution: Use `--width 256 --height 256`
- Reduce scale: Use `--scale 1` instead of larger scales

## Creating Your Own Audio Shaders

### 1. Access Audio Spectrum

```glsl
// Sample audio spectrum (frequency from 0.0 to 1.0)
float amplitude = texture(iChannel0, vec2(frequency, 0.5)).r;
```

### 2. Example: Simple Audio Bars

```glsl
void mainImage(out vec4 fragColor, vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;

    // Sample amplitude at this horizontal position
    float amplitude = texture(iChannel0, vec2(uv.x, 0.5)).r;

    // Draw bar if pixel is below amplitude
    float bar = step(uv.y, amplitude);

    // Color based on frequency
    vec3 col = mix(vec3(1,0,0), vec3(0,0,1), uv.x) * bar;

    fragColor = vec4(col, 1.0);
}
```

### 3. Example: Circular Visualizer

```glsl
void mainImage(out vec4 fragColor, vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    float angle = atan(uv.y, uv.x);
    float freq = (angle / 3.14159 + 1.0) * 0.5; // Map angle to 0-1

    float amplitude = texture(iChannel0, vec2(freq, 0.5)).r;
    float radius = length(uv);

    // Draw ring at amplitude distance
    float ring = smoothstep(0.02, 0.0, abs(radius - amplitude * 0.5));

    vec3 col = vec3(ring);
    fragColor = vec4(col, 1.0);
}
```

## Integration with LED Matrix

To run on Raspberry Pi with LED matrix:

```python
import numpy as np
import piomatter as piomatter

# Create geometry
geometry = piomatter.Geometry(width=64, height=64, n_planes=10, n_addr_lines=5)

# Create framebuffer
framebuffer = np.zeros((geometry.height, geometry.width, 3), dtype=np.uint8)

# Create matrix display
matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=piomatter.Pinout.AdafruitMatrixBonnet,
    framebuffer=framebuffer,
    geometry=geometry
)

# Get GLES renderer with audio
renderer = piomatter.shader.get_renderer(
    width=64, height=64,
    preview=False,  # Use GLES on Pi
    audio_file="audio.mp4"
)

renderer.load_shader("shaders/audio_spectrum.glsl")

# Render loop
while True:
    frame = renderer.render()
    framebuffer[:, :] = frame
    matrix.show()
```

## Performance Notes

- **FFT Size**: 512 samples is a good balance of resolution and performance
- **Texture Upload**: Audio texture (1×512 RGB32F) is small and fast to update
- **Raymarching Cost**: The shader uses 100 iterations - reduce for faster rendering
- **Smoothing**: Temporal smoothing reduces jitter but adds 1 frame latency

## Files

- `src/piomatter/shader/audio_processor.py` - FFT analysis
- `src/piomatter/shader/preview_renderer.py` - Texture binding
- `src/piomatter/shader/cli.py` - `--audio` flag
- `shaders/audio_spectrum.glsl` - Radial visualization shader
- `examples/shader_preview.py` - Preview tool

## References

- FFT (Fast Fourier Transform): https://en.wikipedia.org/wiki/Fast_Fourier_transform
- Raymarching: https://iquilezles.org/articles/raymarchingdf/
- Audio visualization techniques: https://www.shadertoy.com/results?query=audio

---

**TL;DR**: `python examples/shader_preview.py shaders/audio_spectrum.glsl --audio your_audio.mp4` creates a 3D radial audio visualizer you can navigate with arrow keys!
