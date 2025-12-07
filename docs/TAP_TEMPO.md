# Tap Tempo - BPM Control for Shaders

Tap tempo allows you to set the BPM (beats per minute) for shader animations by tapping Pad 8 on your MIDI controller.

## How It Works

1. **Tap Pad 8** on your Minilab3 at a steady tempo (1-4 seconds of tapping)
2. The system calculates BPM from your tap intervals
3. BPM is automatically passed to shaders as `iBPM` and `iBeat` uniforms

## MIDI Setup

- **Controller**: Arturia Minilab3
- **Tap Pad**: Pad 8 (MIDI Note 43)
- **Detection**: Uses last 8 taps for smooth BPM calculation
- **Timeout**: 2 seconds (if you stop tapping, tempo resets)
- **Range**: 20-300 BPM

## Shader Uniforms

Shaders can access tap tempo data via two uniforms:

```glsl
uniform float iBPM;   // Beats per minute (0.0 if no tempo detected)
uniform float iBeat;  // Duration of one beat in seconds (0.0 if no tempo)
```

### Example Usage

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Calculate beat phase (0.0 to 1.0 per beat)
    float beatPhase = mod(iTime, iBeat) / iBeat;

    // Create pulse effect
    float pulse = 1.0 - pow(beatPhase, 2.0);  // Sharp attack, slow decay

    // Use pulse to modulate size, brightness, color, etc.
    float radius = baseRadius * (1.0 + pulse * 0.3);
    vec3 color = baseColor * (0.5 + pulse * 0.5);

    fragColor = vec4(color, 1.0);
}
```

## Example Shaders

### Beat Pulse Sphere
`shaders/primitives/beat_pulse.glsl`

A sphere that pulses in sync with your taps. Controls:
- **param0**: Pulse intensity (0.0 = subtle, 1.0 = intense)
- **param1**: Color hue shift
- **param2**: Base sphere size
- **Pad 8**: Tap to set BPM

### Creating Beat-Synced Effects

Common patterns for beat synchronization:

**1. Basic Pulse (sharp attack, slow decay)**
```glsl
float beatPhase = mod(iTime, iBeat) / iBeat;
float pulse = 1.0 - pow(beatPhase, 2.0);
```

**2. Sawtooth Wave (linear ramp)**
```glsl
float pulse = mod(iTime, iBeat) / iBeat;
```

**3. Sine Wave (smooth oscillation)**
```glsl
float pulse = sin(iTime / iBeat * 6.28318);  // Full cycle per beat
```

**4. Square Wave (on/off)**
```glsl
float pulse = step(0.5, mod(iTime / iBeat, 1.0));
```

**5. Multiple Frequencies**
```glsl
float halfBeat = sin(iTime / iBeat * 2.0 * 6.28318);  // 2x speed
float quarterBeat = sin(iTime / iBeat * 4.0 * 6.28318);  // 4x speed
```

## Testing

Test tap tempo without running the full cube:

```bash
python3 tools/test_tap_tempo.py
```

This will show real-time BPM detection as you tap Pad 8.

## Common BPM Ranges

- **Slow**: 60-80 BPM (1 tap per second)
- **Medium**: 100-120 BPM (2 taps per second)
- **Fast**: 140-160 BPM (2.5 taps per second)
- **Very Fast**: 180+ BPM (3+ taps per second)

## Tips

1. **Consistent Tapping**: Tap at a steady rhythm for accurate BPM detection
2. **More Taps = Better**: System averages last 8 taps for smooth results
3. **2 Second Timeout**: If you stop tapping for 2 seconds, tempo resets
4. **Re-tap Anytime**: You can re-tap at any time to change the tempo
5. **Combine with Params**: Use param0-3 knobs to modulate the beat effects

## Architecture

```
Pad 8 Tap → Note On (43) → TapTempoDetector → BPM Calculation
                                    ↓
                          MIDIUniformSource → iBPM, iBeat
                                    ↓
                          Shader Uniforms → Visual Effects
```

The tap tempo system integrates seamlessly with the existing MIDI parameter system, so you can control BPM with taps while simultaneously controlling other parameters (color, size, intensity) with the knobs.
