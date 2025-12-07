# Beat Trigger System - ADSR Envelope Control

The beat trigger system generates a 0.0-1.0 trigger signal that spikes on each beat with a configurable ADSR envelope.

## Key Changes from BPM System

### Before (BPM uniforms)
- `iBPM`: Actual BPM value (e.g., 120.0)
- `iBeat`: Beat duration in seconds (e.g., 0.5)
- Shader had to calculate beat phase manually
- Pulse happened even with no tempo detected

### After (Beat trigger)
- `iBeatTrigger`: Trigger value 0.0-1.0 that spikes on each beat
- **0.0 when no tempo detected** (shader can check this)
- ADSR envelope with configurable attack/hold/decay
- Knobs 6-8 control envelope shape in real-time

## Controls

### Tap Tempo
- **Pad 8** (Note 43): Tap to set BPM

### Envelope Shaping
- **Knob 6** (CC 18): Attack time (0-500ms)
- **Knob 7** (CC 19): Hold time (0-500ms)
- **Knob 8** (CC 16): Decay time (0-1000ms)

### Shader Parameters
- **Knob 1** (CC 74): param0
- **Knob 2** (CC 71): param1
- **Knob 3** (CC 76): param2
- **Knob 4** (CC 77): param3

## Shader Usage

```glsl
uniform float iBeatTrigger;  // 0.0-1.0 beat trigger

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Check if tempo is detected
    if (iBeatTrigger == 0.0) {
        // No tempo - render static or return black
        fragColor = vec4(0.0);
        return;
    }

    // Use trigger to modulate visuals
    float pulse = iBeatTrigger;  // Already has ADSR envelope applied

    // Example: pulse size
    float size = baseSize * (1.0 + pulse * 0.5);

    // Example: pulse brightness
    vec3 color = baseColor * (0.5 + pulse * 0.5);

    // Example: pulse color
    float hue = mod(baseHue + pulse * 0.2, 1.0);
}
```

## ADSR Envelope Stages

The beat trigger goes through 4 stages per beat:

1. **Attack**: 0.0 → 1.0 (sharp rise)
2. **Hold**: 1.0 (sustained peak)
3. **Decay**: 1.0 → 0.0 (gradual fall)
4. **Silence**: 0.0 (until next beat)

### Envelope Examples

**Sharp Punch** (snare drum feel):
- Attack: 10ms (fast rise)
- Hold: 50ms (brief peak)
- Decay: 100ms (quick drop)

**Smooth Pulse** (bass drum feel):
- Attack: 50ms (gradual rise)
- Hold: 100ms (sustained)
- Decay: 400ms (slow fade)

**Staccato** (hi-hat feel):
- Attack: 5ms (instant)
- Hold: 20ms (very brief)
- Decay: 50ms (quick cut)

## Testing

Test beat trigger without running the full cube:

```bash
python3 tools/test_beat_trigger.py
```

This will show:
1. Real-time BPM detection
2. Beat trigger bar (visual representation)
3. Current envelope settings (Attack/Hold/Decay)

**Instructions:**
1. Tap Pad 8 to set tempo
2. Turn knobs 6-8 to adjust envelope
3. Watch the trigger bar pulse on each beat

## Example: Beat Pulse Shader

`shaders/primitives/beat_pulse.glsl`

A sphere that only appears and pulses when tempo is detected:
- Returns black when `iBeatTrigger == 0.0`
- Pulses with configurable ADSR envelope
- Knobs control intensity, color, and size

## Architecture

```
Pad 8 Tap → TapTempoDetector → BPM Calculation
                ↓
         Beat Tracking (internal timer)
                ↓
         ADSR Envelope Generator
         - Attack (CC4 from Knob 6)
         - Hold (CC5 from Knob 7)
         - Decay (CC6 from Knob 8)
                ↓
         iBeatTrigger (0.0-1.0)
                ↓
         Shader Visuals
```

## MIDI Mapping

| Control | CC Number | Target | Range | Purpose |
|---------|-----------|--------|-------|---------|
| Knob 1 | 74 | param0 | 0-127 | Shader param 0 |
| Knob 2 | 71 | param1 | 0-127 | Shader param 1 |
| Knob 3 | 76 | param2 | 0-127 | Shader param 2 |
| Knob 4 | 77 | param3 | 0-127 | Shader param 3 |
| Knob 6 | 18 | attack | 0-500ms | Envelope attack |
| Knob 7 | 19 | hold | 0-500ms | Envelope hold |
| Knob 8 | 16 | decay | 0-1000ms | Envelope decay |
| Pad 8 | Note 43 | - | - | Tap tempo |

## Implementation Details

### Internal CC Mapping
- MIDI CC 18, 19, 16 → Internal CC 4, 5, 6
- MIDI state has 7 channels: 0-3 (params), 4-6 (envelope)

### Envelope Calculation
- Runs at ~100Hz (called every frame)
- Automatically advances to next beat when duration elapses
- Scales envelope to fit within beat duration if needed
- Returns 0.0 if no tempo detected or timeout (2 seconds)

### Beat Timing
- Tracks last beat time internally
- Automatically triggers next beat after beat duration
- Independent of tap input after BPM is established
- Continues until tempo timeout

## Tips

1. **Start Simple**: Use default envelope (50ms/100ms/200ms) first
2. **Match the Music**: Adjust envelope to feel like the music style
3. **Visual Feedback**: Watch the test tool to understand envelope shape
4. **Combine Effects**: Use `iBeatTrigger` with params for complex animations
5. **Check for Zero**: Always check `if (iBeatTrigger == 0.0)` for no-tempo state
