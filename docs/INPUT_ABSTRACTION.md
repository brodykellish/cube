# Input Abstraction System

The input abstraction system provides a clean, extensible interface for handling real-time inputs in shader rendering. It enables multiple input sources (keyboard, audio, camera feeds, etc.) to coexist and update independently while maintaining Shadertoy shader compatibility.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Input Sources](#input-sources)
- [Usage Examples](#usage-examples)
- [Creating Custom Input Sources](#creating-custom-input-sources)
- [Integration with Shaders](#integration-with-shaders)
- [Best Practices](#best-practices)

## Overview

### Design Principles

1. **Separation of Concerns**: Each input source is independent and self-contained
2. **Clean Interface**: All sources implement the same `InputSource` abstract base class
3. **Composability**: Multiple sources can be active simultaneously
4. **Extensibility**: Easy to add new input types without modifying existing code
5. **Shadertoy Compatibility**: Maps cleanly to Shadertoy uniform conventions

### Key Components

```
InputSource (ABC)
├── KeyboardInput
├── AudioFileInput
├── MicrophoneInput
└── CameraInput (future)

InputManager
└── Manages all active input sources
```

## Architecture

### `InputSource` Abstract Base Class

All input sources must implement this interface:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class InputSource(ABC):
    """Abstract base class for real-time input sources."""

    @abstractmethod
    def update(self, dt: float):
        """Update internal state based on elapsed time."""
        pass

    @abstractmethod
    def get_uniforms(self) -> Dict[str, Any]:
        """Return dictionary of uniform name -> value pairs."""
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up resources (close files, devices, etc.)."""
        pass

    def reset(self):
        """Reset input source to initial state (optional)."""
        pass
```

### `InputManager`

The `InputManager` coordinates multiple input sources:

```python
manager = InputManager()

# Add sources
manager.add_source(KeyboardInput())
manager.add_source(AudioFileInput("music.mp3"))

# Update all sources (call every frame)
manager.update(dt)

# Get combined uniforms
uniforms = manager.get_all_uniforms()

# Cleanup
manager.cleanup()
```

## Input Sources

### KeyboardInput

Provides raw directional input as `iInput` uniform.

**Uniforms Provided:**
- `iInput` (vec4): `(left/right, up/down, forward/backward, unused)`

**Example:**

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import KeyboardInput

keyboard = KeyboardInput()

# Update key states
keyboard.set_key_state('up', True)  # Press up key
keyboard.set_key_state('left', True)  # Press left key

# Get uniforms
uniforms = keyboard.get_uniforms()
# uniforms['iInput'] = (-1.0, 1.0, 0.0, 0.0)

keyboard.set_key_state('up', False)  # Release up key
```

**Key Mapping:**
- `left`, `right` → x-axis (-1.0 to 1.0)
- `up`, `down` → y-axis (-1.0 to 1.0)
- `forward` (E), `backward` (C) → z-axis (-1.0 to 1.0)

### AudioFileInput

Provides beat-synchronized audio uniforms from an audio file.

**Uniforms Provided:**
- `iBPM` (float): Detected beats per minute
- `iBeatPhase` (float): Position in current beat cycle (0.0-1.0)
- `iBeatPulse` (float): Pulse on beat (1.0 at beat, decays to 0.0)

**Example:**

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import AudioFileInput

# With auto-detection
audio = AudioFileInput("music.mp3")

# Or with manual BPM
audio = AudioFileInput("music.mp3", bpm=120.0)

# Update (call every frame)
audio.update(dt=0.016)

# Get uniforms
uniforms = audio.get_uniforms()
# uniforms = {'iBPM': 120.0, 'iBeatPhase': 0.35, 'iBeatPulse': 0.2}
```

**Note:** Requires `AudioProcessor` from the shader module. Falls back to simple BPM-based timing if not available.

### MicrophoneInput

Provides real-time audio analysis from system microphone.

**Uniforms Provided:**
- `iBPM` (float): Real-time detected BPM
- `iBeatPhase` (float): Estimated position in beat cycle
- `iBeatPulse` (float): Pulse on detected beats
- `iAudioLevel` (float): Current audio level (0.0-1.0)
- `iAudioSpectrum` (vec4): Frequency bands (bass, low-mid, high-mid, treble)

**Example:**

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import MicrophoneInput

# Use default microphone
mic = MicrophoneInput()

# Or specify device
mic = MicrophoneInput(device_index=1)

mic.update(dt=0.016)
uniforms = mic.get_uniforms()
```

**Note:** Currently a stub implementation. Real-time audio analysis requires `pyaudio` and FFT processing (planned for future release).

### CameraInput (Planned)

Future implementation for camera/video feed input.

**Planned Uniforms:**
- `iChannel0` (texture): Camera feed as texture
- `iCameraResolution` (vec2): Camera resolution

## Usage Examples

### Basic Usage with UnifiedRenderer

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import (
    UnifiedRenderer, AudioFileInput
)

# Create renderer
renderer = UnifiedRenderer(width=64, height=64, windowed=True)

# Load shader
renderer.load_shader("shaders/audio_reactive.glsl")

# Add audio input
audio = AudioFileInput("music.mp3", bpm=120)
renderer.add_input_source(audio)

# Render loop
running = True
while running:
    renderer.render()
    running = renderer.handle_events()

renderer.cleanup()
```

### Multiple Input Sources

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import (
    UnifiedRenderer, AudioFileInput, MicrophoneInput
)

renderer = UnifiedRenderer(64, 64, windowed=True)
renderer.load_shader("shaders/visualizer.glsl")

# Keyboard is added by default, add audio sources
renderer.add_input_source(AudioFileInput("music.mp3"))
renderer.add_input_source(MicrophoneInput())

# Both audio sources will provide uniforms
# Last source wins if there's a conflict
while running:
    renderer.render()
    running = renderer.handle_events()
```

### Manual InputManager Usage

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import (
    InputManager, KeyboardInput, AudioFileInput
)

manager = InputManager()
manager.add_source(KeyboardInput())
manager.add_source(AudioFileInput("beat.mp3", bpm=140))

# Update loop
dt = 0.016  # 60 FPS
manager.update(dt)

# Get all uniforms
uniforms = manager.get_all_uniforms()

# Use uniforms in your shader renderer
# uniforms = {
#     'iInput': (0.0, 0.0, 0.0, 0.0),
#     'iBPM': 140.0,
#     'iBeatPhase': 0.5,
#     'iBeatPulse': 0.0
# }

manager.cleanup()
```

### Offscreen Rendering with Audio

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import (
    UnifiedRenderer, AudioFileInput
)

# Offscreen rendering (no window)
renderer = UnifiedRenderer(width=64, height=64, windowed=False)

renderer.load_shader("shaders/audio_pulse.glsl")
renderer.add_input_source(AudioFileInput("track.mp3"))

# Render frames
for frame in range(1000):
    renderer.render()

    # Get pixels for display or processing
    pixels = renderer.read_pixels()  # numpy array (64, 64, 3)

    # Display on LED matrix, save to file, etc.
    # matrix.show(pixels)

renderer.cleanup()
```

## Creating Custom Input Sources

To create a custom input source, inherit from `InputSource` and implement the required methods:

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import InputSource
import time

class GamepadInput(InputSource):
    """Custom input source for game controller."""

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.joystick_x = 0.0
        self.joystick_y = 0.0
        # Initialize gamepad library...

    def update(self, dt: float):
        """Read gamepad state."""
        # Read joystick values from gamepad
        # self.joystick_x = read_axis(0)
        # self.joystick_y = read_axis(1)
        pass

    def get_uniforms(self) -> Dict[str, Any]:
        """Return gamepad state as uniforms."""
        return {
            'iInput': (self.joystick_x, self.joystick_y, 0.0, 0.0),
            'iGamepadConnected': 1.0,
        }

    def cleanup(self):
        """Close gamepad connection."""
        # Cleanup gamepad resources
        pass

    def reset(self):
        """Reset gamepad state."""
        self.joystick_x = 0.0
        self.joystick_y = 0.0
```

### Usage:

```python
renderer = UnifiedRenderer(64, 64)
renderer.add_input_source(GamepadInput(device_index=0))
```

## Integration with Shaders

### Shadertoy Uniforms

The input abstraction system provides these Shadertoy-compatible uniforms:

#### Standard Uniforms (always available):

```glsl
uniform vec3 iResolution;      // Viewport resolution
uniform float iTime;           // Time since start (seconds)
uniform int iFrame;            // Frame number
uniform vec4 iMouse;           // Mouse state (unused, always (0,0,0,0))
```

#### Camera Uniforms (provided by camera modes):

```glsl
uniform vec3 iCameraPos;       // Camera position
uniform vec3 iCameraRight;     // Camera right vector
uniform vec3 iCameraUp;        // Camera up vector
uniform vec3 iCameraForward;   // Camera forward vector
```

#### Input Uniforms (provided by input sources):

```glsl
// KeyboardInput
uniform vec4 iInput;           // (left/right, up/down, forward/backward, unused)

// AudioFileInput, MicrophoneInput
uniform float iBPM;            // Beats per minute
uniform float iBeatPhase;      // Beat cycle position (0-1)
uniform float iBeatPulse;      // Beat pulse (1.0 on beat, decays)

// MicrophoneInput only
uniform float iAudioLevel;     // Audio level (0-1)
uniform vec4 iAudioSpectrum;   // Frequency bands (bass, low, mid, high)
```

### Shader Examples

#### Using Keyboard Input:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;

    // Get keyboard input
    vec2 input_dir = iInput.xy;  // -1 to 1 for left/right, up/down

    // Move something based on input
    vec2 center = 0.5 + input_dir * 0.3;

    float dist = length(uv - center);
    vec3 color = vec3(1.0 - smoothstep(0.0, 0.2, dist));

    fragColor = vec4(color, 1.0);
}
```

#### Using Audio Input:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;

    // Pulse on beat
    float pulse = iBeatPulse;
    float radius = 0.2 + pulse * 0.3;

    // Color based on beat phase
    vec3 color = vec3(
        sin(iBeatPhase * 6.28),
        cos(iBeatPhase * 6.28),
        sin(iBeatPhase * 6.28 + 2.0)
    ) * 0.5 + 0.5;

    float dist = length(uv - 0.5);
    color *= 1.0 - smoothstep(radius - 0.05, radius + 0.05, dist);

    fragColor = vec4(color, 1.0);
}
```

#### Combining Camera and Audio:

```glsl
// Raymarching SDF with audio reactivity
vec3 ro = iCameraPos;
vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

// Scale scene with beat pulse
float scale = 1.0 + iBeatPulse * 0.3;

// Raymarch with audio-reactive distance field
// ...
```

## Best Practices

### Performance

1. **Minimize Update Overhead**: Only perform necessary calculations in `update()`
2. **Cache Expensive Computations**: Store computed values, update only when needed
3. **Avoid Blocking Operations**: Don't block the render thread in `update()`
4. **Use Appropriate Data Types**: Match uniform types to shader expectations

### Resource Management

1. **Always Cleanup**: Call `cleanup()` when done with input sources
2. **Use Context Managers**: Consider implementing `__enter__`/`__exit__` for RAII
3. **Handle Exceptions**: Gracefully handle device not found, file missing, etc.
4. **Check Availability**: Verify required libraries/devices before initialization

### Uniform Naming

1. **Follow Shadertoy Conventions**: Use `i` prefix (e.g., `iBPM`, `iInput`)
2. **Be Consistent**: Use similar naming patterns for related uniforms
3. **Document Your Uniforms**: Clearly document what each uniform provides

### Input Coordination

1. **Avoid Uniform Conflicts**: If multiple sources provide the same uniform, last wins
2. **Use Unique Names**: Give custom uniforms unique names to avoid conflicts
3. **Test Combinations**: Test your input sources together to ensure they cooperate

### Error Handling

1. **Fail Gracefully**: Provide sensible defaults if input not available
2. **Log Warnings**: Inform users when optional features are unavailable
3. **Validate Input**: Check device indices, file paths, etc. before use

## Architecture Benefits

### For Developers

- **Clean Separation**: Input logic separated from rendering logic
- **Easy Testing**: Each input source can be unit tested independently
- **Code Reuse**: Same input sources work with any renderer
- **Type Safety**: Clear interface contracts via abstract base class

### For Users

- **Flexibility**: Mix and match input sources as needed
- **Extensibility**: Add custom inputs without modifying core code
- **Compatibility**: Shaders work with any input configuration
- **Predictability**: Uniform interface makes behavior consistent

## Future Extensions

### Planned Input Sources

1. **CameraInput**: Webcam/video feed as texture uniform
2. **GamepadInput**: Game controller support (joysticks, buttons)
3. **OSCInput**: Open Sound Control for music software integration
4. **SerialInput**: Arduino/hardware sensor data
5. **NetworkInput**: Remote control via network sockets

### Potential Enhancements

1. **Input Recording/Playback**: Record input sequences for deterministic replay
2. **Input Smoothing**: Built-in filtering for noisy inputs
3. **Input Mapping**: Remap input ranges and apply curves
4. **Input Composition**: Combine multiple sources with custom logic

## See Also

- `docs/CAMERA_MODES.md` - Camera navigation documentation
- `docs/SHADER_INPUT.md` - Shader input system overview
- `src/adafruit_blinka_raspberry_pi5_piomatter/shader/input_sources.py` - Implementation
- `src/adafruit_blinka_raspberry_pi5_piomatter/shader/unified_renderer.py` - Renderer integration
