# LED Cube Parameter System

## Overview

The LED cube visualization system uses 8 shader parameters (iParam0-7) that can be controlled in real-time from multiple input sources: keyboard, MIDI controllers, audio signals, and web API.

## Parameter Architecture

### Parameter Naming Conventions

The system uses three naming layers:

- **MIDI layer**: CC 0-7 (MIDI Control Change channels)
- **Config layer**: param0-7 (YAML configuration files)
- **Shader layer**: iParam0-7 (GLSL uniform names, following Shadertoy convention)

**Mapping**: `CC N → paramN → iParamN`

### Standard Parameters

| Parameter | Purpose | Range | Control |
|-----------|---------|-------|---------|
| iParam0 | Generic parameter 0 | 0.0 - 1.0 | Keyboard: n/m |
| iParam1 | Generic parameter 1 | 0.0 - 1.0 | Keyboard: ,/. |
| iParam2 | Generic parameter 2 | 0.0 - 1.0 | Keyboard: ;/' |
| iParam3 | Generic parameter 3 | 0.0 - 1.0 | Keyboard: [/] |
| iParam4 | Generic parameter 4 | 0.0 - 1.0 | Keyboard: Shift+n/m |
| iParam5 | Generic parameter 5 | 0.0 - 1.0 | Keyboard: Shift+,/. |
| iParam6 | Generic parameter 6 | 0.0 - 1.0 | Keyboard: Shift+;/' |
| **iParam7** | **Master Effect Intensity** | 0.0 - 1.0 | Keyboard: Shift+[/] |

### iParam7: Master Effect Intensity

**Convention**: iParam7 is designated as the **master effect intensity** control for all effects.

**Purpose**: Provides a single control to fade all effects in/out during live performance. Essential for smooth transitions between presets.

**Usage in Shaders**:
```glsl
// In effect shaders, multiply effect strength by iParam7
vec3 effect = applyEffect(color);
color = mix(color, effect, iParam7);  // iParam7 = 0: no effect, iParam7 = 1: full effect
```

**MIDI Mapping**: Typically mapped to knob 8 on MIDI controllers (CC 27 → param7 → iParam7)

**Live Performance**: Allows performer to instantly fade all effects to zero for clean visual transitions.

## Parameter Sources and Priority

### Source Priority System

Parameters can be controlled by multiple sources simultaneously. The system uses a priority-based resolution:

| Priority | Source | Description |
|----------|--------|-------------|
| 0 | Keyboard | Discrete increment/decrement controls |
| 100 | MIDI | Continuous control from USB MIDI controllers |
| 200 | Audio | Audio-reactive mappings (overrides all other sources) |

**Higher priority sources override lower priority sources.**

### Example Flow

```
1. Frame starts, iParam0 = 0.3 (previous value)
2. KeyboardHandler checks for n/m keys → no change (priority 0)
3. MIDIHandler reads CC 0 = 85 → iParam0 = 0.67 (priority 100, overrides)
4. AudioHandler checks mapping → iParam0 mapped to u_audio_bass = 0.8 (priority 200, overrides MIDI)
5. Final value: iParam0 = 0.8
```

## Input Sources

### 1. Keyboard Controls

**Regular Keys** (iParam0-3):
- `n` / `m` : Decrease / Increase iParam0
- `,` / `.` : Decrease / Increase iParam1
- `;` / `'` : Decrease / Increase iParam2
- `[` / `]` : Decrease / Increase iParam3

**Shift Keys** (iParam4-7):
- `Shift+n` / `Shift+m` : Decrease / Increase iParam4
- `Shift+,` / `Shift+.` : Decrease / Increase iParam5
- `Shift+;` / `Shift+'` : Decrease / Increase iParam6
- `Shift+[` / `Shift+]` : Decrease / Increase iParam7

**Increment Amount**: ±5 MIDI units (0-127 scale), or approximately ±0.04 in normalized (0.0-1.0) scale

### 2. USB MIDI Controllers

**Default Direct Mapping** (when no config file):
- CC 0-7 map directly to param0-7

**Configured Mapping** (via `midi_config.yml`):
```yaml
device_name: "Minilab3"
mappings:
  - midi_cc: 20  # Physical knob 1
    target: param0
  - midi_cc: 21  # Physical knob 2
    target: param1
  # ... etc for all 8 knobs
```

### 3. Audio-Reactive Control

**Configuration** (via `audio_mapping.yml`):
```yaml
mappings:
  iParam0: u_audio_bass    # Bass frequencies control param0
  iParam1: u_audio_mid     # Mid frequencies control param1
  iParam2: u_audio_high    # High frequencies control param2
  iParam3: u_audio_peak    # Peak level controls param3
```

**Priority**: Audio mappings have highest priority (200) and will override both keyboard and MIDI.

### 4. Web API

**REST Endpoint**: `POST /api/parameters`

**Single Parameter**:
```json
{
  "iParam7": 0.5
}
```

**Batch Update**:
```json
{
  "iParam0": 0.8,
  "iParam1": 0.3,
  "iParam7": 1.0
}
```

**Priority**: Web API writes directly to ParameterStore (bypasses handler priority system). This means API updates can be immediately overridden by MIDI/audio if those sources are active.

## Parameter Locking (Future Enhancement)

**Planned Feature**: Parameter Source Manager

Will allow locking parameters to specific sources:
- Lock iParam7 to web control only (block MIDI/keyboard)
- Display which source currently controls each parameter
- Resolve conflicts when multiple sources compete

## Technical Implementation

### MIDIState Class

Location: `/Users/brody/k/nye/cube/src/cube/midi/midi_state.py`

```python
# Default: 8 channels for param0-7
midi_state = MIDIState(num_channels=8)

# Set parameter value
midi_state.set_cc(0, 85)  # Set CC 0 (param0) to 85 (0-127)

# Get normalized value
value = midi_state.get_normalized(0)  # Returns 0.67 (85/127)
```

**Important**: If `num_channels < 8`, parameters 4-7 will silently fail! The fix ensures default is 8.

### ParameterStore Class

Location: `/Users/brody/k/nye/cube/src/cube/render/parameter_store.py`

```python
# Create parameter store (8 params initialized)
parameter_store = ParameterStore()

# Set parameter value
parameter_store.set_parameter_value('iParam7', 0.8)

# Get all parameters for shader
uniforms = parameter_store.get_all_parameters()
# Returns: {'iParam0': 0.0, 'iParam1': 0.0, ..., 'iParam7': 0.8, 'iTime': 42.5, ...}
```

### Validation

```python
# Validate parameter configuration
issues = parameter_store.validate_parameters()
if issues:
    print("Parameter validation warnings:")
    for issue in issues:
        print(f"  - {issue}")
```

## Usage Examples

### Example 1: Live Performance Preset

**Scenario**: Psychedelic shader with glitch effect, controlled by MIDI knobs

```yaml
# preset.yml
sources:
  - type: shader
    shader_path: shaders/graphics/psychedelic.glsl
effects:
  - action: TOGGLE_GLITCH
    enabled: true
```

**MIDI Controller Setup**:
- Knob 1 (CC 20 → param0): Psychedelic intensity
- Knob 2 (CC 21 → param1): Psychedelic speed
- Knob 3 (CC 22 → param2): Glitch frequency
- Knob 8 (CC 27 → param7): Master intensity (fade all effects)

**Performance**:
1. Start with param7 = 0 (no effects visible)
2. Slowly increase param7 to fade in effects
3. Adjust individual effect parameters with knobs 1-3
4. Quick fade to black by dropping param7 to 0

### Example 2: Audio-Reactive Visualization

```yaml
# audio_mapping.yml
mappings:
  iParam0: u_audio_bass     # Bass drives kaleidoscope zoom
  iParam1: u_audio_mid      # Mids drive rotation speed
  iParam2: u_audio_high     # Highs drive color shift
  iParam7: u_audio_peak     # Peak controls master intensity
```

**Result**: Visualization automatically responds to music, with peak detection controlling overall effect intensity.

### Example 3: Web API Control

```python
import requests

# Gradually fade in effects
for intensity in range(0, 101, 5):
    requests.post('http://localhost:5001/api/parameters', json={
        'iParam7': intensity / 100.0
    })
    time.sleep(0.1)
```

## Troubleshooting

### Issue: Parameters 4-7 Not Responding

**Symptom**: Only iParam0-3 work, iParam4-7 stuck at 0.0

**Cause**: MIDIState initialized with `num_channels=4` (old default)

**Fix**: ✅ Fixed in this release - default is now 8 channels

**Verification**:
```bash
python3 cube_control.py
# Check console for:
# [VIZ] All parameters validated successfully
```

### Issue: Web API Parameters Immediately Overridden

**Symptom**: Set parameter via API, but value changes immediately

**Cause**: MIDI or audio source has higher priority and is active

**Solution** (current workaround):
1. Temporarily disable MIDI controller
2. Or disable audio mappings
3. Or use web API to continuously update (poll-based control)

**Future Solution**: Use Parameter Source Manager to lock parameters to web control

### Issue: Keyboard Input Requires Shift Key

**Symptom**: Must hold Shift to control parameters

**Cause**: Key mapping bug in pyglet_keyboard.py

**Fix**: ✅ Fixed in this release - context-aware key mapping

## Future Enhancements

### Planned Features

1. **Parameter Source Manager**
   - Visual indicator of active source per parameter
   - Parameter locking (e.g., lock to web API only)
   - Conflict resolution UI

2. **Parameter Expansion**
   - Support for 16+ parameters (design allows easy expansion)
   - Per-effect parameter sets (effects have their own params)

3. **Parameter Presets**
   - Save/load parameter snapshots
   - Morph between presets
   - Sequence automation

4. **MIDI Learn**
   - Click parameter → move MIDI knob → auto-map
   - No manual YAML editing required

## References

- **MIDIState**: `src/cube/midi/midi_state.py`
- **ParameterStore**: `src/cube/render/parameter_store.py`
- **MIDI Config**: `midi_config.yml`
- **Audio Mapping**: `audio_mapping.yml`
- **Keyboard Bindings**: `src/cube/input/keyboard_source.py`
