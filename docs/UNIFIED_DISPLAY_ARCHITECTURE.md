# Unified Display Architecture

## Overview

The unified display architecture provides a single, cohesive system for rendering both menus and shader visualizations. This document describes the layered display system, shader integration, and how components work together.

## Architecture Components

### 1. LayeredDisplayBackend

**File**: `src/adafruit_blinka_raspberry_pi5_piomatter/menu/layered_backend.py`

Multi-layer framebuffer system with automatic composition. Supports overlaying UI elements (debug info, FPS counters, etc.) on top of base content (menus or shaders).

**Key Features**:
- Multiple independent framebuffer layers
- Automatic layer composition (black pixels treated as transparent in overlays)
- Platform-independent (works with both pygame and piomatter backends)
- Zero-copy layer access for performance

**API**:
```python
from src.adafruit_blinka_raspberry_pi5_piomatter.menu import LayeredDisplayBackend

# Create display with 2 layers
display = LayeredDisplayBackend(width=64, height=64, num_layers=2)

# Get layer framebuffers
base_layer = display.get_layer(0)  # Main content
overlay_layer = display.get_layer(1)  # Debug UI

# Render to layers
base_layer[:] = menu_pixels
overlay_layer[:] = debug_ui_pixels

# Composite and display
display.show()
```

**Layer Composition**:
- Layer 0 (base): Opaque, always fully rendered
- Layer 1+ (overlays): Transparent where pixels are black (0, 0, 0)
- Composition order: Base → Overlay 1 → Overlay 2 → ...

### 2. ShaderMode

**File**: `src/adafruit_blinka_raspberry_pi5_piomatter/menu/shader_integration.py`

Manages in-process shader rendering within the cube control system. Wraps the shader renderer and provides integration with the layered display.

**Key Features**:
- Lazy initialization (shader renderer created on first use)
- Renders shader output to provided framebuffer
- Event handling for shader interactions
- Statistics tracking (FPS, frame count, etc.)

**API**:
```python
from src.adafruit_blinka_raspberry_pi5_piomatter.menu import ShaderMode

# Initialize shader mode
shader_mode = ShaderMode(width=64, height=64, preview=True)

# Load shader
shader_mode.load_shader("shaders/flame.glsl")

# Render loop
while running:
    shader_mode.render_to_framebuffer(framebuffer)
    running = shader_mode.handle_events()

# Cleanup
shader_mode.cleanup()
```

**Current Implementation**:
- Uses PreviewRenderer internally which creates a separate OpenGL window
- Future versions will implement true single-window rendering
- Works seamlessly on both macOS (pygame) and Raspberry Pi (piomatter)

### 3. CubeController

**File**: `src/adafruit_blinka_raspberry_pi5_piomatter/menu/controller.py`

Main controller orchestrating the menu system, shader visualization, and display management.

**Architecture**:
```
CubeController
├── LayeredDisplayBackend (2 layers)
│   ├── Layer 0: Main content (menu or shader)
│   └── Layer 1: Overlay (debug UI)
├── MenuRenderer → renders to Layer 0
├── ShaderMode → renders to Layer 0
├── Menu States (MainMenu, ShaderBrowser, SettingsMenu)
└── Settings (debug_ui, etc.)
```

**Workflow**:

1. **Menu Mode**:
   - MenuRenderer draws menu UI to Layer 0
   - Layer 1 is cleared (no overlay)
   - Display shows composited result

2. **Shader Mode**:
   - ShaderMode renders shader to Layer 0
   - If debug_ui enabled: FPS counter rendered to Layer 1
   - Display shows composited result

3. **State Transitions**:
   - Menu → Shader: Load shader, enter shader render loop
   - Shader → Menu: Cleanup shader resources, return to menu

## Usage Examples

### Basic Menu System

```python
from src.adafruit_blinka_raspberry_pi5_piomatter.menu import CubeController

# Initialize controller
controller = CubeController(width=64, height=64, fps=30, preview=True)

# Run main loop
controller.run()
```

### Shader Visualization with Debug UI

```python
# Enable debug UI in settings menu
# Then select a shader from the browser
# FPS counter will be overlaid on shader output
```

### Custom Overlay Rendering

```python
# In CubeController
def _render_custom_overlay(self):
    """Render custom UI overlay."""
    overlay_renderer = MenuRenderer(self.overlay_layer)

    # Draw custom text
    overlay_renderer.draw_text("CUSTOM UI", x=10, y=10, color=(255, 255, 0))

    # Draw shapes
    overlay_renderer.draw_rect(x=5, y=5, width=50, height=20,
                               color=(100, 100, 100), filled=False)
```

## Platform Compatibility

### macOS / Development (pygame backend)

- **Menu Rendering**: pygame 2D primitives + numpy framebuffer
- **Shader Rendering**: OpenGL in separate pygame window (temporary)
- **Composition**: Layers composited in numpy, displayed via pygame

### Raspberry Pi / LED Cube (piomatter backend)

- **Menu Rendering**: Direct framebuffer operations
- **Shader Rendering**: OpenGL ES rendering to framebuffer
- **Composition**: Layers composited in numpy, output to LED matrix

## Future Enhancements

### Single-Window OpenGL Rendering

**Current**: Menu uses pygame 2D, shaders use separate OpenGL window

**Future**: Unified OpenGL rendering
- Initialize pygame window with OPENGL flag
- Render menu as OpenGL textures
- Render shaders to same OpenGL context
- Overlay debug UI using OpenGL text rendering
- Single window for everything

**Implementation Path**:
1. Convert MenuRenderer to use OpenGL primitives (quads, textures)
2. Implement OpenGL text rendering (bitmap font as texture atlas)
3. Modify ShaderMode to share main window's OpenGL context
4. Remove PreviewRenderer window creation

### Advanced Layer Features

**Alpha Blending**:
```python
# Support semi-transparent overlays
layer_alpha = 0.7
result = cv2.addWeighted(base_layer, 1.0, overlay_layer, layer_alpha, 0)
```

**Blend Modes**:
- Additive: Useful for glow effects
- Multiply: Useful for shadows/tinting
- Screen: Useful for highlights

**Layer Effects**:
- Gaussian blur for backgrounds
- Color grading/LUTs
- Real-time filters

### GPU Acceleration (Raspberry Pi)

- Use GPU for layer composition (faster than numpy)
- Hardware-accelerated blending modes
- Real-time effects with OpenGL shaders

## Performance Considerations

### Memory Usage

**Per-layer overhead**:
- 64×64 RGB: 12 KB per layer
- 128×128 RGB: 48 KB per layer
- 256×256 RGB: 192 KB per layer

**Optimization tips**:
- Use minimum number of layers needed
- Clear overlay layers when not in use (reduces composition overhead)
- Reuse layer framebuffers instead of reallocating

### Frame Rate

**Composition overhead**:
- Numpy-based composition: ~0.1-0.5ms for 64×64, ~1-2ms for 128×128
- Negligible compared to display refresh (typically 16-33ms for 30-60 FPS)

**Bottlenecks**:
- Shader rendering: GPU-bound
- Display output: Limited by hardware refresh rate (piomatter) or pygame blit (preview)

## Troubleshooting

### Two Windows Appearing (macOS)

**Symptom**: Both menu window and shader window visible

**Cause**: Current implementation uses separate window for OpenGL shader rendering

**Workaround**: This is expected behavior in current version. Future versions will use single window.

**Solution**: Focus on shader window during visualization, menu window returns after exiting shader.

### Layer Composition Issues

**Symptom**: Overlay not appearing or flickering

**Possible causes**:
1. Overlay layer not being cleared between frames
2. Overlay pixels are pure black (treated as transparent)
3. Composition not being called before display

**Solutions**:
```python
# Always clear overlay at start of frame
self.overlay_layer[:, :] = 0

# Use non-black colors for overlay content
overlay_renderer.draw_text("FPS", color=(0, 255, 0))  # Not (0, 0, 0)

# Ensure show() is called (handles composition automatically)
self.display.show()
```

### Performance Degradation

**Symptom**: Frame rate drops when overlay enabled

**Possible causes**:
1. Too many overlay elements
2. Complex text rendering
3. Layer composition overhead

**Solutions**:
- Limit overlay updates to once per second (e.g., FPS counter)
- Use smaller scale for overlay text
- Profile with `cProfile` to identify bottlenecks

## API Reference

### LayeredDisplayBackend

```python
class LayeredDisplayBackend:
    def __init__(self, width: int, height: int, num_layers: int = 2, **kwargs)
    def get_layer(self, index: int) -> np.ndarray
    def clear_layer(self, index: int, color=(0, 0, 0))
    def clear_all_layers(self, color=(0, 0, 0))
    def compose_layers(self) -> np.ndarray
    def show()
    def handle_events() -> dict
    def cleanup()
```

### ShaderMode

```python
class ShaderMode:
    def __init__(self, width: int, height: int, preview: bool = False,
                 show_fps: bool = False, **kwargs)
    def load_shader(self, shader_path: str)
    def render_to_framebuffer(self, framebuffer: np.ndarray)
    def handle_events() -> bool
    def get_stats() -> dict
    def cleanup()
```

### CubeController

```python
class CubeController:
    def __init__(self, width: int, height: int, fps: int = 30, **kwargs)
    def run()
    # Internal methods:
    def _handle_state_transition(self, next_state: str) -> bool
    def _launch_shader_visualization(self, shader_path: str)
    def _render_debug_overlay()
```

## Related Documentation

- `CUBE_CONTROL.md` - Main cube control system documentation
- `SHADER_README.md` - Shader system overview
- `LOCAL_DEVELOPMENT.md` - Development setup guide
- `KEYBOARD_NAVIGATION.md` - Shader navigation controls
