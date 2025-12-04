# USB MIDI Controller Setup

This guide explains how to use a physical USB MIDI controller (with faders, knobs, buttons) to control shader parameters.

## Installation

Install the required Python library:

```bash
pip install python-rtmidi
```

## Quick Start

1. **Plug in your MIDI controller** via USB

2. **Discover your controller's CC numbers** using the MIDI monitor tool:
   ```bash
   python tools/midi_monitor.py
   ```

   Move your faders and knobs to see which CC numbers they send.

3. **Edit `midi_config.yml`** in the project root:
   ```yaml
   device_name: "auto"  # or your device name

   mappings:
     - midi_cc: 74      # Replace with your fader's CC
       target: param0
     - midi_cc: 71
       target: param1
     - midi_cc: 76
       target: param2
     - midi_cc: 77
       target: param3
   ```

4. **Run the cube controller**:
   ```bash
   python cube_control.py --v2
   ```

5. **Move your controller's faders/knobs** - shader parameters update in real-time!

## Configuration

### Device Selection

**Auto mode (recommended for single controller):**
```yaml
device_name: "auto"
```

**Specific device:**
```yaml
device_name: "Arturia MiniLab mkII"
```
The device name must match (case-insensitive) part of the device name shown by `midi_monitor.py`.

### CC Mappings

Each mapping connects a MIDI CC number from your controller to a shader parameter:

```yaml
mappings:
  - midi_cc: 74        # CC number from your controller
    target: param0     # Shader parameter (param0, param1, param2, param3)
    min: 0             # Optional: minimum MIDI value (default: 0)
    max: 127           # Optional: maximum MIDI value (default: 127)
```

**Parameter meanings:**
- `param0` - Often red, rotation speed, or primary effect control
- `param1` - Often green, secondary effect, or brightness
- `param2` - Often blue, tertiary effect, or size
- `param3` - Often shape, ratio, or quaternary control

Check individual shader source code to see what each parameter controls.

### Multiple Controllers

You can map multiple CC numbers to the same parameter (last value wins):

```yaml
mappings:
  - midi_cc: 74
    target: param0
  - midi_cc: 1   # Mod wheel also controls param0
    target: param0
```

### Value Ranges

Clamp MIDI input to a specific range:

```yaml
mappings:
  - midi_cc: 74
    target: param0
    min: 32      # Ignore values below 32
    max: 96      # Ignore values above 96
```

## Common MIDI Controllers

### Arturia MiniLab mkII
- Faders: CC 48-55
- Knobs: CC 74, 71, 76, 77, 93, 73, 75, 114

### Akai MPD218
- Knobs: CC 3, 9, 12-15
- Faders: CC 1, 2

### Novation Launchpad
- Knobs: CC 21-28

### MIDI Fighter Twister
- Knobs: CC 0-63

Use `midi_monitor.py` to discover your specific controller's CC numbers.

## Troubleshooting

### "No MIDI devices found"
- Check USB connection
- On Linux, you may need to add your user to the `audio` group:
  ```bash
  sudo usermod -a -G audio $USER
  ```
  Then log out and back in.

### "python-rtmidi not installed"
- Install with: `pip install python-rtmidi`
- On Raspberry Pi, you may need: `sudo apt-get install libasound2-dev`

### Controller not responding
- Check device name in `midi_config.yml` matches output of `midi_monitor.py`
- Verify CC numbers are correct
- Some controllers need to be put in "CC mode" (check controller manual)

### Values jumping around
- Check that your controller is sending CC messages (not notes)
- Use `midi_monitor.py` to verify the controller is sending expected values

## Architecture

The USB MIDI system integrates with the existing MIDI parameter system:

```
USB MIDI Controller → USBMIDIDriver → MIDIState → MIDIUniformSource → Shaders
Keyboard (n,m,etc) → MIDIKeyboardDriver → ↑
```

Both keyboard emulation and USB MIDI update the same `MIDIState`, so they work together seamlessly.

## Example: Pyramid Shader

With the pyramid shader (`shaders/primitives/pyramid.glsl`):
- **param0 (CC 74)** - Red channel (0.0 to 1.0)
- **param1 (CC 71)** - Green channel (0.0 to 1.0)
- **param2 (CC 76)** - Blue channel (0.0 to 1.0)
- **param3 (CC 77)** - Height ratio (0.0 = flat, 1.0 = height equals base area)

Map your controller's faders to these CCs and you can paint the pyramid in real-time!
