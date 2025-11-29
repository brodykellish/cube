# Shader Input System

The unified shader renderer provides a hybrid input system that gives shaders flexible access to both raw input and precomputed camera vectors.

## Available Uniforms

### Core Shadertoy Uniforms

```glsl
uniform vec3 iResolution;     // Viewport resolution (width, height, 1.0)
uniform float iTime;          // Time in seconds since shader loaded
uniform float iTimeDelta;     // Time since last frame
uniform int iFrame;           // Frame number
uniform vec4 iMouse;          // Mouse position (currently always 0,0,0,0)
```

### Texture Samplers

```glsl
uniform sampler2D iChannel0;  // Texture channel 0
uniform sampler2D iChannel1;  // Texture channel 1
uniform sampler2D iChannel2;  // Texture channel 2
uniform sampler2D iChannel3;  // Texture channel 3
```

Textures are loaded automatically from files named:
- `shader_name.channel0` (or `.png`, `.jpg`, etc.)
- `shader_name.channel1`
- etc.

### Raw Input (NEW)

```glsl
uniform vec4 iInput;  // (left/right, up/down, forward/backward, unused)
```

Values range from -1.0 to +1.0 for each axis:
- `iInput.x`: Horizontal input (left=-1.0, right=+1.0)
- `iInput.y`: Vertical input (down=-1.0, up=+1.0)
- `iInput.z`: Depth input (backward=-1.0, forward=+1.0)
- `iInput.w`: Reserved (currently 0.0)

**Perfect for game controllers**: Analog sticks naturally map to these ranges!

### Precomputed Camera (Convenience)

```glsl
uniform vec3 iCameraPos;      // Camera position in world space
uniform vec3 iCameraRight;    // Camera right vector (normalized)
uniform vec3 iCameraUp;       // Camera up vector (normalized)
uniform vec3 iCameraForward;  // Camera forward vector (normalized)
```

These are computed from keyboard input using spherical coordinates (yaw/pitch/distance).

**Most shaders should use these** - they provide smooth camera rotation without writing camera code.

### Audio Reactive (Optional)

```glsl
uniform float iBPM;           // Detected beats per minute (0.0 if no audio)
uniform float iBeatPhase;     // 0-1 position within current beat cycle
uniform float iBeatPulse;     // 1.0 on beat, decays to 0
```

Requires audio file to be provided when initializing the shader renderer.

## Usage Patterns

### Pattern 1: Standard Camera (Recommended for Most Shaders)

Use precomputed camera vectors for raymarching:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Ray origin and direction using precomputed camera
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // Your raymarching code here
    vec3 col = raymarch(ro, rd);

    fragColor = vec4(col, 1.0);
}
```

**Benefits:**
- No camera code needed
- Smooth rotation from keyboard/controller
- Works immediately

### Pattern 2: Custom Input Handling

Access raw input for game-like behavior:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;

    // Use raw input for custom effects
    float rotation = iInput.x * iTime;  // Spin based on horizontal input
    float zoom = 5.0 + iInput.y * 3.0;  // Zoom with vertical input

    // Rotate coordinates
    float c = cos(rotation);
    float s = sin(rotation);
    vec2 rotUV = vec2(
        uv.x * c - uv.y * s,
        uv.x * s + uv.y * c
    );

    // Your effect here
    vec3 col = myEffect(rotUV, zoom);

    fragColor = vec4(col, 1.0);
}
```

**Benefits:**
- Full control over input behavior
- Great for 2D effects and games
- Game controller friendly

### Pattern 3: Audio Reactive

React to music beats:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    vec3 col = raymarch(ro, rd);

    // Pulse brightness on beats
    col *= (1.0 + iBeatPulse * 0.5);

    // Modulate hue with beat phase
    col = rotateHue(col, iBeatPhase * 6.28318);

    fragColor = vec4(col, 1.0);
}
```

**Benefits:**
- Visual sync with music
- Beat detection handled automatically
- BPM tracking

### Pattern 4: Hybrid (Mix and Match)

Combine approaches for maximum flexibility:

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use precomputed camera for base view
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // But add custom input-based effects
    float wobble = sin(iTime + iInput.x * 10.0) * 0.1;
    rd = normalize(rd + vec3(0, wobble, 0));

    vec3 col = raymarch(ro, rd);

    // Audio-reactive brightness
    col *= (1.0 + iBeatPulse * 0.3);

    fragColor = vec4(col, 1.0);
}
```

## Keyboard Controls (Default)

When running through cube control menu:

- **Arrow Keys / WASD**: Rotate camera (yaw/pitch)
- **E / C**: Zoom in/out
- **ESC**: Exit shader mode
- **R**: Reload shader

These map to:
- Left/Right → `iInput.x` and camera yaw
- Up/Down → `iInput.y` and camera pitch
- E/C → `iInput.z` and camera distance

## Game Controller Support

The `iInput` uniform is designed for game controllers:

```
Left Analog Stick:
├─ X-axis → iInput.x (left/right)
└─ Y-axis → iInput.y (up/down)

Right Analog Stick / Triggers:
└─ Could map to iInput.z (forward/backward)
```

This makes it easy to create immersive, game-like experiences on the LED cube.

## Audio Integration

To enable audio-reactive shaders, pass an audio file when initializing:

```python
renderer = UnifiedShaderRenderer(
    width=64,
    height=64,
    audio_file="music.mp3"  # Enable audio processing
)
```

The renderer will:
1. Analyze the audio for beats
2. Track BPM automatically
3. Provide beat phase and pulse timing
4. Update uniforms in real-time

## Migration from Old Shaders

If you have shaders that used only `iMouse` or no input:

**Old approach (no input):**
```glsl
vec3 ro = vec3(0, 0, -5);
vec3 rd = normalize(vec3(uv, 1.0));
```

**New approach (use precomputed camera):**
```glsl
vec3 ro = iCameraPos;
vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
```

Your shader now has smooth keyboard/controller navigation!

## Best Practices

1. **Start with precomputed camera** - easiest to use, works for 90% of shaders
2. **Use raw input for 2D effects** - when you don't need 3D camera
3. **Add audio reactivity last** - after shader looks good, enhance with audio
4. **Test with different input devices** - keyboard, game controller, etc.
5. **Provide defaults** - shader should look good even with zero input

## Examples

See the `shaders/` directory for examples:
- Most shaders use precomputed camera (`iCameraPos`, etc.)
- Some use custom effects (can be adapted to use `iInput`)
- Audio-reactive examples (when available)
