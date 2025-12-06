# Xbox Controller Setup Guide

## Overview

Your LED cube now supports Xbox controllers (and most USB gamepads) for smooth, analog camera control. This provides much better control than keyboard tapping!

## Hardware Support

### Tested Controllers
- **Original Xbox Controller** (wired USB)
- Xbox 360 Controller (wired)
- Xbox One Controller (wired/wireless with adapter)
- Most generic USB gamepads

### Requirements
- USB connection to computer
- macOS or Linux with pygame support
- No additional drivers needed (plug and play)

## Setup

### 1. Plug In Controller

```bash
# Plug in Xbox controller via USB
# No drivers needed on macOS/Linux
```

### 2. Test Detection

```bash
# Run test script to verify controller is detected
python scripts/test_gamepad.py
```

Expected output:
```
Connected to: Microsoft X-Box pad v1 (US)
  Axes: 6
  Buttons: 10
  Hats: 1

LIVE AXIS VALUES (move sticks to see values)
Axis0: +0.00  Axis1: -0.15  Axis2: +0.80  Axis3: -0.50
```

### 3. Run Cube Control

```bash
# Controller is automatically detected
python cube_control.py --width 1024 --height 512 --scale 4
```

If controller is detected, you'll see:
```
✓ Gamepad detected and enabled for camera control
```

## Controller Layout

### Original Xbox Controller

```
        [LB]                                    [RB]

    ┌─────────┐                          (Y)
    │ D-Pad   │                      (X)     (B)
    └─────────┘                          (A)

   ╭───────╮                            ╭───────╮
   │  L👍  │                            │  R👍  │
   ╰───────╯                            ╰───────╯
   Left Stick                          Right Stick
```

### Control Mapping

| Input | Camera Action | Details |
|-------|---------------|---------|
| **Left Stick →/←** | Yaw (rotate horizontally) | Smooth analog rotation |
| **Left Stick ↑/↓** | Pitch (rotate vertically) | Smooth analog rotation |
| **Right Stick ↑/↓** | Zoom in/out | Smooth analog zoom |
| **Right Stick →/←** | (Reserved/Shift mode) | Currently unused |

### Sensitivity

- **Deadzone**: 15% (prevents stick drift)
- **Rotation sensitivity**: 1.5x
- **Zoom sensitivity**: 1.0x

## Usage

### Basic Camera Control

1. Launch any shader visualization
2. Use **left stick** to look around
3. Use **right stick up/down** to zoom in/out
4. Works alongside keyboard controls (both active simultaneously)

### Example Session

```bash
python cube_control.py --width 1024 --height 512 --scale 4

# In menu: Navigate to Visualize → PRIMITIVES → sphere
# The visualization launches

# Now you can:
# - Move left stick to rotate view
# - Move right stick up/down to zoom
# - Still use WASD if you prefer
# - All inputs work together
```

## Integration Details

### Input Combination

The system combines **keyboard + gamepad** inputs:
- If keyboard W is held OR left stick is pushed up → camera rotates up
- Both inputs are additive
- Smooth analog values from gamepad
- Digital values from keyboard

### Architecture

**File**: `src/cube/input/gamepad.py`
- `GamepadCameraInput` class
- Polls pygame joystick API
- Maps axes to camera input state
- Applies deadzone filtering

**Integration**: `src/cube/controller.py`
- Auto-detects gamepad on startup
- Polls every frame during visualization
- Combines with keyboard input
- Updates camera uniform source

## Troubleshooting

### Controller Not Detected

```bash
# Run test script
python scripts/test_gamepad.py

# If no joysticks found:
# 1. Check USB connection
# 2. Try different USB port
# 3. Check System Preferences → Security (macOS)
# 4. Try: sudo python scripts/test_gamepad.py
```

### Axes Are Reversed/Wrong

Different controllers have different axis mappings. Edit `src/cube/input/gamepad.py`:

```python
# Original Xbox mapping:
left_x = self.joystick.get_axis(0)   # Left stick horizontal
left_y = self.joystick.get_axis(1)   # Left stick vertical
right_x = self.joystick.get_axis(2)  # Right stick horizontal
right_y = self.joystick.get_axis(3)  # Right stick vertical

# If your controller is different, swap these axis numbers
```

### Stick Drift

If camera moves when sticks are centered:

1. **Increase deadzone** in `gamepad.py`:
```python
self.deadzone = 0.20  # Default: 0.15
```

2. Or calibrate controller in System Settings

### Too Sensitive / Not Sensitive Enough

Adjust sensitivity in `gamepad.py`:

```python
self.rotation_sensitivity = 2.0  # Default: 1.5 (higher = faster rotation)
self.zoom_sensitivity = 1.5      # Default: 1.0 (higher = faster zoom)
```

## Advanced Configuration

### Custom Axis Mapping

For non-Xbox controllers, you may need to remap axes. Run the test script to see which axis is which:

```bash
python scripts/test_gamepad.py
# Move each stick and note which axis number changes
```

Then edit `gamepad.py` with the correct axis indices.

### Button Mapping (Future)

Currently only analog sticks are used. Potential future mappings:
- **A/B/X/Y buttons**: Parameter control
- **Triggers**: Sensitivity/speed adjustment
- **D-Pad**: Discrete camera presets
- **Start/Back**: Reset camera / toggle modes

## Compatibility

| Controller | Status | Notes |
|------------|--------|-------|
| **Original Xbox (wired)** | ✅ Tested | Your controller! |
| Xbox 360 (wired) | ✅ Should work | Standard HID device |
| Xbox One (wired) | ✅ Should work | Standard HID device |
| PS4/PS5 DualShock | ✅ Should work | May need axis remapping |
| Generic USB gamepad | ⚠️ Probably works | May need axis remapping |
| Wireless (Bluetooth) | ⚠️ Untested | May require pairing |

## Testing

With controller plugged in:

```bash
# 1. Test detection
python scripts/test_gamepad.py

# 2. Test in cube
python cube_control.py

# 3. Launch a shader, move sticks
# You should see smooth camera rotation!
```

## Next Steps

- Try it with your Xbox controller
- Adjust deadzone/sensitivity if needed
- Report which axis mapping works best
- Consider adding button mappings for parameters
