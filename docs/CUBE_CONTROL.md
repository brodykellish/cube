# Cube Control - Master Control System

`cube-control` is the master control script for the LED cube, providing a unified menu interface for visualization selection and system settings.

## Features

- **Platform-Independent**: Automatically uses pygame (development) or piomatter (LED cube)
- **Primitive Rendering**: Uses numpy framebuffer operations (no OpenGL) for LED matrix compatibility
- **Extensible Menu System**: Clean state-based architecture for adding new modes
- **Shader Browser**: Visual interface for selecting and launching shader visualizations
- **Settings Management**: Framework for system configuration (stub implemented)

## Quick Start

### Basic Usage

```bash
# Run with default settings (64×64)
python cube_control.py

# Specify custom resolution
python cube_control.py --width 128 --height 64

# Force preview mode (pygame) even on Raspberry Pi
python cube_control.py --preview
```

### Navigation

**Main Menu**:
- **Up/Down** or **W/S**: Navigate menu options
- **Enter**: Select option
- **ESC** or **Q**: Quit

**Shader Browser**:
- **Up/Down** or **W/S**: Scroll through shaders
- **Enter**: Launch selected shader
- **ESC** or **B**: Return to main menu

**During Shader Visualization**:
- **ESC** or **Q**: Return to menu
- **R**: Reload shader
- **Arrow Keys/WASD**: Navigate camera (shader-dependent)

## Command-Line Options

### Display Options

```bash
--width WIDTH, -w WIDTH
    Display width in pixels (default: 64)

--height HEIGHT
    Display height in pixels (default: 64)

--fps FPS
    Target frames per second for menu rendering (default: 30)
    Note: Shader visualizations use their own FPS setting

--preview
    Force preview mode (pygame) even on Raspberry Pi
```

### Hardware Options (Raspberry Pi Only)

```bash
--pinout PINOUT
    Hardware pinout configuration
    Options: AdafruitMatrixBonnet, AdafruitMatrixHatRGB, AdafruitMatrixHatBGR
    Default: AdafruitMatrixBonnet

--num-planes PLANES
    Color depth in bit-planes (4-11)
    Default: 10

--num-address-lines LINES
    Address lines: 4 for 32-pixel tall panels, 5 for 64-pixel tall
    Default: 4
```

## Architecture

### Components

**cube_control.py**
- Main entry point
- Command-line argument parsing
- Creates and runs CubeController

**menu/** Module
- `controller.py`: Main control loop, state management, shader launching
- `display_backend.py`: Abstraction for pygame/piomatter rendering
- `menu_renderer.py`: Primitive drawing operations (text, rectangles, lines)
- `menu_states.py`: Menu state classes (MainMenu, ShaderBrowser, SettingsMenu)

### Display Backend

The display backend automatically selects the appropriate renderer:

**Pygame (Development)**:
- Detected on macOS/Windows
- Creates scaled window for easy viewing
- Full keyboard support

**Piomatter (Production)**:
- Detected on Raspberry Pi with LED matrix hardware
- Direct rendering to LED matrix
- Optimized for low latency

### Menu System

The menu system uses a state-based architecture:

```
MainMenu
├─> Visualize (ShaderBrowser)
│   └─> Launch Shader → shader_preview.py subprocess
└─> Settings (SettingsMenu) [stub]
```

Each state implements:
- `render(renderer)`: Draw UI to framebuffer
- `handle_input(key)`: Process input and return next state

## Examples

### Development Workflow

```bash
# Test menu system on macOS with large window
python cube_control.py --width 64 --height 64

# Test with different resolution
python cube_control.py --width 128 --height 32 --fps 60
```

### Production Deployment (Raspberry Pi)

```bash
# Run on LED cube with default settings
python cube_control.py

# Run with custom hardware configuration
python cube_control.py \
    --width 128 \
    --height 64 \
    --pinout AdafruitMatrixHatRGB \
    --num-planes 11 \
    --num-address-lines 5
```

## Adding New Menu States

To add a new menu mode:

1. **Create State Class** in `menu_states.py`:

```python
class MyNewState(MenuState):
    def __init__(self):
        self.selected = 0

    def render(self, renderer: MenuRenderer):
        renderer.clear((0, 0, 10))
        renderer.draw_text_centered("MY NEW MODE", y=5, color=(100, 200, 255))
        # ... draw your UI

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        if key == 'escape':
            return 'main'  # Return to main menu
        # ... handle other inputs
        return None
```

2. **Register State** in `controller.py`:

```python
self.states = {
    'main': MainMenu(),
    'visualize': ShaderBrowser(width, height),
    'settings': SettingsMenu(),
    'mynewmode': MyNewState(),  # Add your state
}
```

3. **Add Menu Option** in `MainMenu`:

```python
self.options = [
    ("VISUALIZE", "visualize"),
    ("MY NEW MODE", "mynewmode"),  # Add option
    ("SETTINGS", "settings"),
]
```

## Menu Renderer API

The `MenuRenderer` provides primitive drawing operations:

```python
# Clear screen
renderer.clear(color=(0, 0, 0))

# Draw text
renderer.draw_text("HELLO", x=10, y=10, color=(255, 255, 255), scale=1)
renderer.draw_text_centered("CENTERED", y=20, color=(200, 200, 200))

# Draw rectangles
renderer.draw_rect(x=10, y=10, width=30, height=20, color=(255, 0, 0), filled=True)

# Draw lines
renderer.draw_line(x1=0, y1=0, x2=63, y2=63, color=(0, 255, 0))

# Draw scrollbar
renderer.draw_scrollbar(x=60, y=10, height=40, position=5,
                       total_items=20, visible_items=10)
```

## Bitmap Font

The menu system uses a custom 5×7 pixel bitmap font optimized for LED matrices:
- Monospace design
- High legibility at low resolution
- Supports A-Z, 0-9, and common symbols
- Scalable (scale=1: 5×7, scale=2: 10×14, etc.)

## Troubleshooting

### "No shaders found"

Ensure `shaders/` directory exists and contains `.glsl` files:

```bash
ls shaders/*.glsl
```

### Pygame window too small/large

Adjust scale in `display_backend.py` or specify smaller resolution:

```bash
python cube_control.py --width 32 --height 32
```

### Shader won't launch

Check that `examples/shader_preview.py` exists and is executable:

```bash
python examples/shader_preview.py --shader shaders/flame.glsl --width 64 --height 64
```

### Permission denied on Raspberry Pi

Ensure user has access to `/dev/pio0`:

```bash
sudo usermod -aG gpio $USER
# Reboot required
```

## Future Enhancements

- **GPIO Button Support**: Physical button navigation for the cube
- **Settings Menu**: Functional brightness, FPS, resolution controls
- **Audio Visualizer Mode**: Direct integration without subprocess
- **Playlist Mode**: Auto-cycle through shaders
- **Custom Shader Parameters**: UI for adjusting shader uniforms
- **System Status**: Display FPS, temperature, memory usage

## Related Documentation

- `SHADER_README.md` - Shader system overview
- `KEYBOARD_NAVIGATION.md` - Shader navigation controls
- `LOCAL_DEVELOPMENT.md` - Development setup guide
