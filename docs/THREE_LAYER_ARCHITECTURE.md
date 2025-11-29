# Three-Layer Display Architecture

## Overview

The cube control system uses a 3-layer framebuffer architecture for compositing different visual elements. Each layer serves a specific purpose and they are composited in order (bottom to top).

## Layer Stack

```
┌─────────────────────────────┐
│  Layer 2: Debug Overlay     │  ← Top (always visible on top)
│  - FPS counter              │
│  - Debug information        │
│  - Stats display            │
├─────────────────────────────┤
│  Layer 1: Shader            │  ← Middle
│  - GLSL shader output       │
│  - 3D visualizations        │
│  - Real-time graphics       │
├─────────────────────────────┤
│  Layer 0: Menu              │  ← Bottom
│  - Main menu                │
│  - Shader browser           │
│  - Settings                 │
└─────────────────────────────┘
```

## Layer Details

### Layer 0: Menu Layer (`menu_layer`)
- **Purpose**: UI menus and navigation
- **Active when**: In menu mode (not viewing shaders)
- **Rendered by**: `MenuRenderer` (bitmap font, primitives)
- **Content**:
  - Main menu (VISUALIZE, SETTINGS, EXIT)
  - Shader browser list
  - Settings menu

**When active**: Layer 1 and 2 are cleared

### Layer 1: Shader Layer (`shader_layer`)
- **Purpose**: Shader visualization output
- **Active when**: In shader mode (viewing a shader)
- **Rendered by**: `UnifiedShaderRenderer` (OpenGL → readback to numpy)
- **Content**:
  - Real-time GLSL shader rendering
  - 3D visualizations
  - Procedural graphics

**When active**: Layer 0 is cleared, Layer 2 may have debug info

### Layer 2: Debug Layer (`debug_layer`)
- **Purpose**: Always-on-top debug information
- **Active when**: Debug UI enabled in settings
- **Rendered by**: `MenuRenderer` (text rendering)
- **Content**:
  - FPS counter (green text, top-left)
  - Performance stats
  - Other debug information

**Transparency**: Black pixels (0,0,0) are transparent

## Composition Process

### In Menu Mode

```python
# Clear unused layers
shader_layer[:, :] = 0     # Not rendering shader
debug_layer[:, :] = 0      # No debug in menu mode

# Render menu
menu_renderer.render(menu_layer)

# Composite: Only menu layer has content
display.show()  # menu + black + black = menu
```

### In Shader Mode (Debug OFF)

```python
# Clear unused layers
menu_layer[:, :] = 0       # Not showing menu
debug_layer[:, :] = 0      # Debug disabled

# Render shader
shader_renderer.render()
pixels = shader_renderer.read_pixels()
shader_layer[:, :] = pixels

# Composite: Only shader layer has content
composited = compose_layers()  # black + shader + black = shader
display_with_opengl(composited)
```

### In Shader Mode (Debug ON)

```python
# Clear menu layer
menu_layer[:, :] = 0       # Not showing menu

# Render shader
shader_renderer.render()
pixels = shader_renderer.read_pixels()
shader_layer[:, :] = pixels

# Render debug overlay
debug_renderer.render_fps(debug_layer)

# Composite: Shader + debug overlay on top
composited = compose_layers()  # black + shader + debug = shader with FPS
display_with_opengl(composited)
```

## Composition Algorithm

From `LayeredDisplayBackend.compose_layers()`:

```python
def compose_layers(self):
    # Start with layer 0 (bottom)
    result = layers[0].copy()

    # Overlay each subsequent layer
    for i in range(1, num_layers):
        layer = layers[i]

        # Create mask: True where layer is non-black
        mask = np.any(layer != 0, axis=2, keepdims=True)

        # Apply layer where mask is True
        result = np.where(mask, layer, result)

    return result
```

**Key point**: Black pixels `(0, 0, 0)` in upper layers are treated as transparent, allowing lower layers to show through.

## Usage Example

### Enable Debug Overlay

1. Start cube-control: `python cube_control.py --width 128 --height 128`
2. Navigate to **SETTINGS**
3. Select **DEBUG UI** and press Enter to toggle **ON**
4. Press ESC to return to main menu
5. Navigate to **VISUALIZE**
6. Select any shader
7. **Result**: Shader renders on Layer 1, FPS counter appears on Layer 2 (on top)

### Layer Visibility

| Mode | Layer 0 (Menu) | Layer 1 (Shader) | Layer 2 (Debug) |
|------|----------------|------------------|-----------------|
| Main Menu | ✓ Visible | ✗ Black | ✗ Black |
| Shader Browser | ✓ Visible | ✗ Black | ✗ Black |
| Settings Menu | ✓ Visible | ✗ Black | ✗ Black |
| Shader (Debug OFF) | ✗ Black | ✓ Visible | ✗ Black |
| Shader (Debug ON) | ✗ Black | ✓ Visible | ✓ Visible (on top) |

## Performance

**Memory Usage** (per frame):
- 128×128 resolution: 3 layers × 128 × 128 × 3 bytes = 144 KB
- 64×64 resolution: 3 layers × 64 × 64 × 3 bytes = 36 KB

**Composition Time**:
- 128×128: ~1-2 ms (numpy operations)
- 64×64: ~0.2-0.5 ms

**Total overhead**: Minimal compared to shader rendering time (16ms @ 60 FPS)

## Adding More Layers

To add additional layers:

1. **Increase layer count**:
```python
self.display = LayeredDisplayBackend(width, height, num_layers=4)
```

2. **Get new layer reference**:
```python
self.custom_layer = self.display.get_layer(3)
```

3. **Render to new layer**:
```python
custom_renderer = MenuRenderer(self.custom_layer)
custom_renderer.draw_text("Custom Info", x=10, y=10)
```

4. **Composition is automatic** - `compose_layers()` handles all layers

## Future Enhancements

### GPU-Accelerated Composition

Currently using numpy for CPU-side composition. Could be moved to GPU:

```glsl
// Fragment shader for layer composition
uniform sampler2D layer0;  // Menu
uniform sampler2D layer1;  // Shader
uniform sampler2D layer2;  // Debug

void main() {
    vec4 result = texture2D(layer0, texCoord);

    vec4 shader = texture2D(layer1, texCoord);
    if (shader.rgb != vec3(0.0)) result = shader;

    vec4 debug = texture2D(layer2, texCoord);
    if (debug.rgb != vec3(0.0)) result = debug;

    gl_FragColor = result;
}
```

### Alpha Blending

Instead of black = transparent, support true alpha channel:

```python
# Layer with alpha
layer_rgba = np.zeros((height, width, 4), dtype=np.uint8)
layer_rgba[y, x] = [255, 0, 0, 128]  # 50% transparent red

# Composition with alpha blending
result = alpha_blend(base, overlay, overlay_alpha)
```

## Related Documentation

- `UNIFIED_DISPLAY_ARCHITECTURE.md` - Overall architecture
- `CUBE_CONTROL.md` - Main cube control documentation
- `FIXES_SUMMARY.md` - Recent fixes and improvements
