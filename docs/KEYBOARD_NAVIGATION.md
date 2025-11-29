# Keyboard Navigation for Shaders

This library supports smooth, velocity-based keyboard navigation in shaders, allowing you to create explorable 3D scenes with fluid camera movement.

## How It Works

The preview renderer captures keyboard input, integrates it into smooth velocity-based motion, and passes both raw input and accumulated camera position to your shader:

### Available Uniforms

```glsl
uniform vec4 iInput;      // Raw input state (left/right, up/down, forward/backward, unused)
uniform vec3 iCameraPos;  // Accumulated camera position (smooth velocity-based movement)
```

### Input Values

**`iInput` - Raw keyboard state:**
- `iInput.x`: Left/Right (-1.0 when LEFT/A pressed, +1.0 when RIGHT/D pressed, 0.0 otherwise)
- `iInput.y`: Up/Down (-1.0 when DOWN/C pressed, +1.0 when UP/E pressed, 0.0 otherwise)
- `iInput.z`: Forward/Backward (-1.0 when BACK/S pressed, +1.0 when FORWARD/W pressed, 0.0 otherwise)
- `iInput.w`: Reserved for future use (currently 0.0)

**`iCameraPos` - Smooth camera position:**
- Automatically accumulated from keyboard input over time
- Uses velocity-based physics with acceleration and damping
- Provides smooth, inertial camera movement
- Initial position: `(0.0, 0.0, 5.0)`

### Controls

**Navigation Keys:**
- Arrow Keys or WASD: Move Forward/Back/Left/Right
- PageUp/E: Move Up
- PageDown/C: Move Down

**Other Controls:**
- ESC or Q: Quit
- R: Restart (reset time)

## Example Shader

See `shaders/navigate.glsl` for a complete example. Here's a minimal example:

```glsl
void mainImage(out vec4 fragColor, vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use the smooth accumulated camera position
    // This automatically has velocity-based physics built in!
    vec3 cameraPos = iCameraPos;

    // Camera target (looking at origin)
    vec3 target = vec3(0.0, 0.0, 0.0);

    // Setup camera ray
    vec3 forward = normalize(target - cameraPos);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
    vec3 up = cross(forward, right);
    vec3 rd = normalize(uv.x * right + uv.y * up + 1.5 * forward);

    // Your raymarching/rendering code here
    // ...
}
```

The camera movement is automatically smooth because `iCameraPos` is accumulated with velocity physics in the renderer!

## Usage

Run the shader preview with keyboard navigation:

```bash
python examples/shader_preview.py --shader shaders/navigate.glsl --width 512 --height 512
```

Press arrow keys or WASD to navigate through the 3D scene!

## Porting to Raspberry Pi with Game Controller

The keyboard input system is designed to be easily adapted for game controllers on Raspberry Pi:

1. Create a custom input driver that reads from your game controller
2. Map controller inputs to the same `iInput` uniform format
3. The shader code remains unchanged!

### Example Controller Mapping

```python
# Pseudo-code for game controller integration
input_state = {
    'left': controller.dpad_left or controller.joystick_x < -0.5,
    'right': controller.dpad_right or controller.joystick_x > 0.5,
    'up': controller.dpad_up or controller.joystick_y > 0.5,
    'down': controller.dpad_down or controller.joystick_y < -0.5,
    'forward': controller.button_a,
    'backward': controller.button_b,
}
```

## Physics Parameters

The smooth camera movement uses these physics parameters (configurable in `preview_renderer.py`):

- **`camera_speed`**: Base movement speed (default: 3.0 units/second)
- **`camera_damping`**: Velocity decay rate (default: 0.9)
  - 0.0 = instant stop
  - 1.0 = no damping (infinite glide)
  - 0.9 = realistic "friction"

### How It Works

1. **Acceleration**: Keyboard input applies acceleration to velocity
2. **Velocity Integration**: Position is updated based on velocity each frame
3. **Damping**: Velocity decays over time for natural deceleration
4. **Frame-rate Independent**: Uses delta-time for consistent motion at any FPS

This creates smooth, inertial camera movement that feels natural and responsive!

## Tips for Shader Development

1. **Test on macOS first**: Develop and test your navigation shaders using the preview renderer on macOS
2. **Just use `iCameraPos`**: No need for complex integration in your shader - it's already smooth!
3. **Use visual feedback**: Add debug overlays to visualize camera position (see navigate.glsl example)
4. **Adjust physics**: Modify `camera_speed` and `camera_damping` in the renderer for different feel

## Future Enhancements

Potential improvements:
- Persistent camera state (position accumulation across frames)
- Mouse look controls
- Configurable input sensitivity
- Multiple input profiles (FPS, flying, orbit, etc.)
