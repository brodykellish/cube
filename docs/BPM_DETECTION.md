# BPM Detection System

Automatic beat detection and BPM (beats per minute) estimation for audio-reactive shaders.

## Overview

The BPM detection system analyzes audio in real-time to:
- **Detect beats** (kick drum hits, snare hits, etc.)
- **Estimate BPM** (tempo of the music)
- **Track beat phase** (position within the current beat cycle)
- **Provide beat pulse** (sharp attack on each beat)

This allows shaders to synchronize visual effects with the music's rhythm.

## How It Works

### 1. Energy-Based Beat Detection

The system monitors low-frequency energy (bass) to detect beats:

```python
# Calculate energy in bass frequencies (first 10% of spectrum)
bass_bins = int(spectrum_size * 0.1)
energy = sum(spectrum[:bass_bins] ** 2)

# Smooth energy to reduce noise
smoothed_energy = 0.7 * prev_energy + 0.3 * current_energy

# Detect beat: energy spike above threshold
if smoothed_energy > threshold and prev_energy <= threshold:
    beat_detected = True
```

**Key parameters:**
- **Bass frequency range**: First 10% of spectrum (typically 0-2 kHz)
- **Energy threshold**: 1.3× average energy
- **Minimum beat interval**: 0.3 seconds (prevents false positives above 200 BPM)

### 2. BPM Estimation

BPM is estimated from intervals between detected beats:

```python
# Record beat timestamps
beat_times.append(current_time)

# Calculate intervals between recent beats
intervals = diff(beat_times)

# Filter outliers (0.3s - 2.0s = 30-200 BPM range)
valid_intervals = [i for i in intervals if 0.3 < i < 2.0]

# Estimate BPM from median interval
avg_interval = median(valid_intervals)
bpm = 60.0 / avg_interval
```

**Smoothing:**
- Uses median of last 8 beat intervals (robust to outliers)
- Requires at least 4 beats before estimating BPM
- Confidence increases as more beats are detected

### 3. Beat Phase Tracking

Beat phase (0-1) indicates position within the current beat cycle:

```python
time_since_beat = current_time - last_beat_time
beat_phase = (time_since_beat / beat_interval) % 1.0
```

- `0.0` = exactly on the beat
- `0.5` = halfway between beats
- `0.99` = just before the next beat

### 4. Beat Pulse

Sharp attack signal that triggers on each beat:

```python
# Set to 1.0 when beat detected
beat_pulse = 1.0 on beat

# Decay exponentially
beat_pulse = max(0.0, beat_pulse - decay_rate * dt)
```

Decay rate of 5.0 means the pulse drops to ~0 within 0.2 seconds.

## Shader Integration

### Available Uniforms

The BPM system exposes three uniforms to shaders:

```glsl
uniform float iBPM;        // Detected BPM (e.g., 120.0)
uniform float iBeatPhase;  // 0-1 position in beat cycle
uniform float iBeatPulse;  // 1.0 on beat, decays to 0
```

### Usage Examples

#### Pulsing Circle

```glsl
void mainImage(out vec4 fragColor, vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    float dist = length(uv);

    // Circle size pulses with beat phase
    float pulse = sin(iBeatPhase * 6.28318) * 0.5 + 0.5;
    float circleSize = 0.3 + pulse * 0.2;

    // White flash on each beat
    float flash = iBeatPulse;

    // Render
    float circle = smoothstep(circleSize + 0.05, circleSize, dist);
    vec3 col = vec3(circle) + flash * vec3(1.0);

    fragColor = vec4(col, 1.0);
}
```

#### Expanding Rings

```glsl
// Rings expand from center with each beat
float rings = fract(dist * 8.0 - iBeatPhase * 2.0);
rings = smoothstep(0.0, 0.1, rings) * smoothstep(0.3, 0.2, rings);
```

#### Color Cycling

```glsl
// Cycle through color spectrum over each beat
vec3 color1 = vec3(1.0, 0.3, 0.5);  // Pink
vec3 color2 = vec3(0.3, 0.8, 1.0);  // Cyan

vec3 color;
if (iBeatPhase < 0.5) {
    color = mix(color1, color2, iBeatPhase * 2.0);
} else {
    color = mix(color2, color1, (iBeatPhase - 0.5) * 2.0);
}
```

#### Rotation Speed

```glsl
// Rotate at exactly 1 revolution per beat
float angle = iBeatPhase * 6.28318;  // 2π radians per beat
vec2 rotated = vec2(
    uv.x * cos(angle) - uv.y * sin(angle),
    uv.x * sin(angle) + uv.y * cos(angle)
);
```

#### Intensity Modulation

```glsl
// Brightness pulses with music
float brightness = 0.5 + iBeatPulse * 0.5;
col *= brightness;
```

## Example Shaders

### beat_pulse.glsl

Demonstrates all BPM features:
- Pulsing central circle
- Expanding rings
- Color cycling through spectrum
- Beat indicator flash

Run with:
```bash
python examples/shader_preview.py shaders/beat_pulse.glsl \
    --audio your_music.mp3 \
    --width 512 --height 512
```

### audio_spectrum.glsl (enhanced)

The audio spectrum visualizer now includes beat highlights:
- White flash on peaks when beat detected
- Synchronized with frequency visualization

## Tuning Parameters

### Sensitivity

Adjust threshold in `audio_processor.py`:

```python
# More sensitive (detects more beats, may have false positives)
self.energy_threshold = 1.2

# Less sensitive (only strong beats)
self.energy_threshold = 1.5
```

### BPM Range

Adjust interval filtering:

```python
# Wider BPM range (20-300 BPM)
valid_intervals = [i for i in intervals if 0.2 < i < 3.0]

# Narrower range (60-150 BPM, typical for most music)
valid_intervals = [i for i in intervals if 0.4 < i < 1.0]
```

### Decay Speed

Adjust beat pulse decay in `audio_processor.py`:

```python
# Slower decay (pulse lasts longer)
decay_rate = 3.0

# Faster decay (sharp, brief pulse)
decay_rate = 8.0
```

## Performance Notes

- **CPU cost**: Minimal (energy calculation is simple sum)
- **Accuracy**: Works best with music that has clear, consistent beats (EDM, rock, pop)
- **Latency**: ~1-2 frames (16-33ms at 60fps)
- **Adaptation time**: Requires 4+ beats to stabilize BPM estimate (~2-5 seconds)

## Limitations

### What Works Well:
- Music with clear, consistent beats (EDM, house, techno, rock, pop)
- Four-on-the-floor rhythms
- Music with prominent kick drum or bass

### What's Challenging:
- Complex polyrhythms (e.g., jazz, prog rock)
- Variable tempo (rubato, tempo changes)
- Music without bass/drums (classical, ambient)
- Syncopated rhythms (funk, breakbeat)

## Accessing BPM Info in Python

```python
# Get BPM information
bpm_info = audio_processor.get_bpm_info()

print(f"BPM: {bpm_info['bpm']:.1f}")
print(f"Beat Phase: {bpm_info['beat_phase']:.2f}")
print(f"Beat Pulse: {bpm_info['beat_pulse']:.2f}")
print(f"Confidence: {bpm_info['confidence']:.2f}")
```

## Advanced: Custom Beat Synchronization

### Quantize to Beat Grid

```glsl
// Snap animation to beat boundaries
float quantized = floor(iBeatPhase * 4.0) / 4.0;  // 4 steps per beat
```

### Trigger Events on Specific Beats

```glsl
// Trigger every 4th beat (once per bar in 4/4 time)
float barPhase = mod(iTime * (iBPM / 60.0), 4.0);
bool downbeat = barPhase < 1.0;
```

### Predict Next Beat

```glsl
// Time until next beat (in seconds)
float timeToNextBeat = (1.0 - iBeatPhase) * (60.0 / iBPM);

// Anticipation effect (ramp up before beat)
float anticipation = smoothstep(0.3, 0.0, timeToNextBeat);
```

## Troubleshooting

### BPM Not Detecting

**Symptoms**: BPM stays at 120, no beat pulses

**Solutions**:
1. Check audio is loading (should see "Loaded X.Xs of audio")
2. Increase sensitivity: `energy_threshold = 1.1`
3. Ensure music has prominent bass/kick drum
4. Wait 5-10 seconds for detection to stabilize

### False Beat Detections

**Symptoms**: Beat pulse triggers too frequently, incorrect BPM

**Solutions**:
1. Decrease sensitivity: `energy_threshold = 1.5`
2. Check audio quality (clipping/distortion can cause false positives)
3. Increase minimum beat interval if detecting double-beats

### BPM Drifts Over Time

**Symptoms**: BPM estimate changes during playback

**Solutions**:
1. Normal for music with tempo changes (intentional)
2. For consistent tempo music, increase BPM history length
3. Check for audio buffer underruns (playback skips)

## Future Enhancements

Potential improvements:
- Multi-band onset detection (detect different instruments)
- Downbeat detection (first beat of measure)
- Time signature estimation (3/4, 4/4, 6/8, etc.)
- Autocorrelation-based tempo estimation
- Machine learning-based beat tracking

## Files

- `src/piomatter/shader/audio_processor.py` - BPM detection logic
- `src/piomatter/shader/preview_renderer.py` - Uniform binding
- `src/piomatter/shader/renderer.py` - Uniform declarations
- `shaders/beat_pulse.glsl` - Example beat-synchronized shader
- `shaders/audio_spectrum.glsl` - Spectrum with beat highlights

---

**TL;DR**: Use `iBPM`, `iBeatPhase`, and `iBeatPulse` uniforms in shaders to synchronize visual effects with music beats!
