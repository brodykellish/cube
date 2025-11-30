# Display Architecture

## Overview

The display system provides a clean, self-contained module for rendering framebuffers to various backends (pygame for development, piomatter for LED hardware). The architecture respects separation of concerns and prevents backend implementation details from leaking into other parts of the system.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Controllers                              │
│                  (menu, shader, etc.)                         │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ├──> Renderers generate pixels
                            │    (numpy arrays)
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Display Module                             │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Multi-Layer Compositor                   │   │
│  │                                                        │   │
│  │  Layer 0 (Bottom): Menu UI                           │   │
│  │  Layer 1 (Middle): Shader output                     │   │
│  │  Layer 2 (Top): Debug overlay                        │   │
│  │                                                        │   │
│  │  Composites layers (black = transparent)             │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                  │
│                            ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Backend Abstraction                      │   │
│  │                                                        │   │
│  │  PygameBackend     │    PiomatterBackend             │   │
│  │  - Regular 2D      │    - LED Matrix                 │   │
│  │  - OpenGL mode     │    - PioMatter driver           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
                    ┌───────────────┐
                    │  Screen / LEDs │
                    └───────────────┘
```

## Key Design Principles

### 1. **Separation of Concerns**

- **Renderers**: Generate pixel data (numpy arrays)
- **Display**: Handles layering, compositing, and backend selection
- **Backends**: Implement platform-specific rendering

### 2. **No Implementation Leakage**

- Controllers never import pygame, OpenGL, or piomatter directly
- All backend-specific code is contained in `display/backends.py`
- Display module exposes a clean, platform-agnostic API

### 3. **Framebuffer-Centric**

- All communication happens via numpy arrays
- Renderers write pixels, display consumes pixels
- Simple, efficient, no complex abstractions

## Module Structure

```
src/piomatter/
├── display/
│   ├── __init__.py           # Public API exports
│   ├── display.py            # Display class (layering, compositing)
│   └── backends.py           # Backend implementations
├── menu/
│   ├── controller.py         # Menu controller
│   ├── menu_renderer.py      # Menu renderer (→ pixels)
│   └── ...
└── shader/
    └── unified_shader_renderer.py  # Shader renderer (→ pixels)
```

## Display API

### Core Class: `Display`

```python
from piomatter.display import Display

# Initialize display with 3 layers
display = Display(
    width=64,
    height=64,
    num_layers=3,
    backend='auto',  # or 'pygame', 'piomatter'
    opengl=False,
    scale=1  # pygame only
)

# Get layer for rendering
layer0 = display.get_layer(0)  # Returns numpy array (height, width, 3)

# Render directly to layer
layer0[10:20, 10:20] = [255, 0, 0]  # Red rectangle

# Or set layer from framebuffer
framebuffer = renderer.read_pixels()
display.set_layer(1, framebuffer)

# Composite and show
display.show()  # Composites all layers and displays

# Event handling
events = display.handle_events()
if events['quit']:
    break
if events['key'] == 'escape':
    do_something()

# OpenGL mode switching (pygame only)
display.enable_opengl()   # Switch to OpenGL
display.disable_opengl()  # Switch back to 2D

# Cleanup
display.cleanup()
```

### Layer System

Layers are composited bottom-to-top with **black pixels (0,0,0) treated as transparent**:

```python
# Layer 0 (bottom): Menu
menu_layer = display.get_layer(0)
menu_renderer.render(menu_layer)

# Layer 1 (middle): Shader
shader_layer = display.get_layer(1)
shader_pixels = shader_renderer.read_pixels()
shader_layer[:, :] = shader_pixels

# Layer 2 (top): Debug overlay
debug_layer = display.get_layer(2)
debug_layer[:, :] = 0  # Clear
debug_renderer.draw_text("FPS 60", x=2, y=2, color=(0, 255, 0))

# Display composites: menu + shader + debug
display.show()
```

**Result**: Shader appears on top of menu (since menu is likely cleared), debug text appears on top of everything.

## Backend Selection

### Auto-Detection

When `backend='auto'` (default), the display automatically selects:

- **macOS / Windows**: pygame backend
- **Linux**:
  - With `/dev/dri/card0` (GPU): pygame backend
  - Without GPU: piomatter backend (assumes LED hardware)

### Manual Selection

```python
# Force pygame for development on RPi
display = Display(width=64, height=64, backend='pygame')

# Force piomatter for LED cube
display = Display(width=64, height=64, backend='piomatter',
                  pinout='AdafruitMatrixBonnet',
                  num_planes=10)
```

## Backends

### Pygame Backend

**Features**:
- Regular 2D rendering (pygame blitting)
- OpenGL rendering (for shader mode)
- Keyboard/mouse input
- Window scaling

**Arguments**:
- `scale`: Window scale factor (default 1)
- `opengl`: Start in OpenGL mode (default False)

**Usage**:
```python
display = Display(width=64, height=64, backend='pygame', scale=2)
```

### Piomatter Backend

**Features**:
- Direct LED matrix output
- PioMatter driver integration
- Hardware-accelerated refresh

**Arguments**:
- `pinout`: Hardware pinout ('AdafruitMatrixBonnet', etc.)
- `num_planes`: Color depth (4-11, default 10)
- `num_address_lines`: Scan rate (4 or 5, default 4)
- `num_temporal_planes`: Temporal dithering (0, 2, or 4)
- `serpentine`: Panel chaining (default True)

**Usage**:
```python
display = Display(
    width=64, height=32,
    backend='piomatter',
    pinout='AdafruitMatrixBonnet',
    num_planes=10,
    num_address_lines=4
)
```

## Renderer Interface

Renderers should expose a `read_pixels()` method that returns a numpy array:

```python
class MyRenderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.framebuffer = np.zeros((height, width, 3), dtype=np.uint8)

    def render(self):
        """Update internal framebuffer."""
        # Draw stuff to self.framebuffer
        pass

    def read_pixels(self) -> np.ndarray:
        """
        Return rendered pixels.

        Returns:
            Numpy array of shape (height, width, 3) with dtype uint8
        """
        return self.framebuffer.copy()
```

**Controller usage**:
```python
# Render and copy to layer
my_renderer.render()
pixels = my_renderer.read_pixels()
display.set_layer(0, pixels)

# Or render directly to layer
layer = display.get_layer(0)
my_renderer.render_to(layer)  # If renderer supports direct rendering
```

## OpenGL Mode Switching

The display system supports dynamic switching between 2D and OpenGL modes (pygame backend only):

```python
# Start in 2D mode
display = Display(width=64, height=64, opengl=False)

# Render menu in 2D
menu_layer = display.get_layer(0)
menu_renderer.render(menu_layer)
display.show()

# Switch to OpenGL for shader
display.enable_opengl()

# Shader renders with OpenGL, reads pixels to layer
shader_renderer.render()  # Uses OpenGL internally
pixels = shader_renderer.read_pixels()
display.set_layer(1, pixels)

# Debug overlay on top
debug_layer = display.get_layer(2)
debug_renderer.render(debug_layer)

# Display composites and renders with OpenGL
display.show()

# Back to 2D mode
display.disable_opengl()
```

**Note**: OpenGL mode is required for GLSL shader rendering. The display module handles the mode switching transparently.

## Example: Complete Workflow

```python
from piomatter.display import Display
from menu.menu_renderer import MenuRenderer
from shader.unified_shader_renderer import UnifiedShaderRenderer

# Initialize display
display = Display(width=64, height=64, num_layers=3)

# Get layers
menu_layer = display.get_layer(0)
shader_layer = display.get_layer(1)
debug_layer = display.get_layer(2)

# Create renderers
menu_renderer = MenuRenderer(menu_layer)
shader_renderer = UnifiedShaderRenderer(64, 64)

# Main loop
while running:
    events = display.handle_events()

    if in_shader_mode:
        # Clear menu, render shader
        menu_layer[:, :] = 0
        shader_renderer.render()
        shader_layer[:, :] = shader_renderer.read_pixels()
    else:
        # Clear shader, render menu
        shader_layer[:, :] = 0
        menu_renderer.render()

    # Always render debug overlay
    debug_layer[:, :] = 0
    if debug_enabled:
        draw_fps(debug_layer)

    # Composite and display
    display.show()

# Cleanup
display.cleanup()
```

## Benefits of This Architecture

1. **Clean Separation**: Renderers don't know about backends, backends don't know about renderers
2. **Easy Testing**: Can swap backends without changing renderer code
3. **Platform Independence**: Same code works on development machines and hardware
4. **No Leakage**: OpenGL, pygame, piomatter never leak into controller code
5. **Simple API**: Just read_pixels() → set_layer() → show()
6. **Efficient**: Direct numpy array manipulation, minimal copying
7. **Extensible**: Easy to add new backends (e.g., web canvas, VNC)

## Related Documentation

- `THREE_LAYER_ARCHITECTURE.md` - Details on layer compositing
- `UNIFIED_DISPLAY_ARCHITECTURE.md` - Previous architecture (superseded)
- `FIXES_SUMMARY.md` - Implementation history
