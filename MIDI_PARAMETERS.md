# MIDI Parameter Control System

## Overview

The MIDI parameter system provides a clean abstraction layer for controlling shader parameters. All parameter control flows through MIDI CC (Control Change) values, whether from a laptop keyboard or USB MIDI device.

## Architecture

```
Keyboard Input → MIDI State (CC0-CC3) ← USB MIDI Device (optional)
                      ↓
               MIDI Uniform Source
                      ↓
            Shader Uniforms (iParam0-iParam3)
```

## Keyboard Controls

When a visualization is running, use these keys to control MIDI parameters:

| Keys | CC Channel | Uniform | Description |
|------|------------|---------|-------------|
| n / m | CC0 | iParam0 | Decrease / Increase parameter 0 |
| , / . | CC1 | iParam1 | Decrease / Increase parameter 1 |
| [ / ] | CC2 | iParam2 | Decrease / Increase parameter 2 |
| ; / ' | CC3 | iParam3 | Decrease / Increase parameter 3 |

Each key press changes the CC value by ±5 (range: 0-127).

## Shader Uniforms

MIDI parameters are available in shaders as:

```glsl
uniform float iParam0;  // Normalized CC0 (0.0-1.0)
uniform float iParam1;  // Normalized CC1 (0.0-1.0)
uniform float iParam2;  // Normalized CC2 (0.0-1.0)
uniform float iParam3;  // Normalized CC3 (0.0-1.0)
uniform vec4 iParams;   // All params as vector (param0, param1, param2, param3)
```

## Example Shader Usage

See `shaders/primitives/sphere_midi.glsl` for a complete example:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Map iParam0 (0.0-1.0) to radius (0.5-5.0)
    float radius = mix(0.5, 5.0, iParam0);

    // Map iParam1 to rotation speed
    float rotationSpeed = mix(0.0, 5.0, iParam1);

    // Map iParam2 to color hue shift
    vec3 color = hueShift(baseColor, iParam2);

    // Map iParam3 to fog density
    float fogDensity = mix(0.0, 0.3, iParam3);

    // ... use parameters in shader
}
```

## Implementation Details

### MIDIState (`src/cube/midi/midi_state.py`)
- Holds current CC values (0-127) for each channel
- Provides `get_cc()` and `get_normalized()` methods
- Thread-safe single source of truth

### MIDIKeyboardDriver (`src/cube/midi/keyboard_driver.py`)
- Maps keyboard keys to MIDI CC changes
- Configurable step size (default: 5)
- Returns True if key was handled (MIDI control key)

### MIDIUniformSource (`src/cube/midi/uniform_source.py`)
- Implements UniformSource interface
- Converts MIDI CC values to shader uniforms
- Normalizes CC values (0-127) to (0.0-1.0)

## Future Enhancements

### USB MIDI Device Support

Create `USBMIDIInput` class:

```python
import rtmidi  # or mido library

class USBMIDIInput:
    def __init__(self, midi_state: MIDIState):
        self.midi_state = midi_state
        self.midi_in = rtmidi.MidiIn()
        self.midi_in.open_port(0)

    def poll(self):
        """Read MIDI messages and update state."""
        message = self.midi_in.get_message()
        if message:
            # Parse CC message and update midi_state
            pass
```

### Per-Shader Parameter Metadata

Add comments to shaders describing what each parameter controls:

```glsl
// @param iParam0 float 0.5 5.0 "Sphere radius"
// @param iParam1 float 0.0 5.0 "Rotation speed"
// @param iParam2 float 0.0 1.0 "Color hue shift"
// @param iParam3 float 0.0 0.3 "Fog density"
```

Parse these for UI display and validation.

### Parameter Saving/Loading

Save MIDI parameter presets per shader:

```json
{
  "sphere_midi.glsl": {
    "presets": {
      "default": [64, 64, 64, 64],
      "large_slow": [120, 20, 0, 80],
      "small_fast": [20, 120, 50, 10]
    }
  }
}
```

## Testing

Run `cube_control.py` and select a primitive shader:
1. Launch visualization (VISUALIZE → SURFACE → sphere_midi)
2. Press `m` several times - radius increases
3. Press `.` several times - rotation speeds up
4. Press `]` - colors shift
5. Press `'` - fog thickens

Watch console for feedback: `MIDI: param0 = 89 (0.70)`
