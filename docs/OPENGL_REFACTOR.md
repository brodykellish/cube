# OpenGL Mode Refactor

## Problem

The pygame window was being switched to OpenGL mode (DOUBLEBUF | OPENGL) when rendering shaders, which caused several issues:

1. **FPS Overlay Not Visible**: Text rendering and pixel compositing didn't work correctly in OpenGL mode
2. **Leaky Abstraction**: The display backend was exposing OpenGL details to the controller
3. **Unnecessary Complexity**: Shader renderer already reads pixels back to numpy, so OpenGL window mode wasn't needed

## Root Cause

The shader renderer needed an OpenGL context to render GLSL shaders. Initially, this context was provided by switching the main pygame window to OpenGL mode. However, this approach had problems:

- Pygame in OpenGL mode requires using OpenGL commands for all rendering (including text and UI)
- The FPS overlay was being rendered to a layer, but the composited result wasn't displaying correctly
- The coordinate systems and rendering paths were different between 2D and OpenGL modes

## Solution

**Separate the OpenGL context from the display window:**

1. **Shader Renderer**: Creates its own offscreen OpenGL context using GLUT
2. **Display Backend**: Always stays in regular pygame 2D mode
3. **Workflow**: Shader renders with OpenGL → reads pixels to numpy → display composites layers → pygame blits pixels

##Architecture Changes

### Before

```
Main Pygame Window
├─ Regular Mode (for menu)
│  └─ Pygame blitting
└─ OpenGL Mode (for shaders)
   └─ glDrawPixels rendering
   └─ FPS overlay broken

Shader Renderer
└─ Uses pygame's OpenGL context
```

### After

```
Main Pygame Window
└─ Always Regular Mode
   └─ Pygame blitting (works for everything)
   └─ FPS overlay works correctly

Shader Renderer
└─ Own offscreen OpenGL context (GLUT)
   └─ Renders to hidden window
   └─ Reads pixels back to numpy
```

## Key Changes

### 1. Display Backend Simplified

**`display/backends.py`**:
- Removed OpenGL mode entirely from PygameBackend
- Removed `_init_opengl_mode()`, `enable_opengl()`, `disable_opengl()`, `_show_opengl()`
- Always uses regular pygame blitting via `_show_regular()`

```python
class PygameBackend:
    def __init__(self, width, height, scale=1, **kwargs):
        # Always create regular window (no OpenGL flags)
        self.screen = pygame.display.set_mode((width, height))

    def show(self, framebuffer):
        # Always use pygame blitting
        surface = pygame.surfarray.make_surface(framebuffer)
        self.screen.blit(surface, (0, 0))
        pygame.display.flip()
```

### 2. Display Module Cleaned

**`display/display.py`**:
- Removed `opengl` parameter from `__init__`
- Removed `enable_opengl()` and `disable_opengl()` methods
- Simplified initialization

```python
class Display:
    def __init__(self, width, height, num_layers=1, backend='auto', **kwargs):
        # No OpenGL mode tracking
        self.backend = create_backend(backend, width, height, **kwargs)
```

### 3. Shader Renderer Independence

**`menu/unified_shader_renderer.py`**:
- Added `_init_opengl_context()` to create offscreen context via GLUT
- No longer depends on pygame window being in OpenGL mode
- Completely self-contained

```python
class UnifiedShaderRenderer:
    def __init__(self, width, height):
        # Create own OpenGL context
        self._init_opengl_context()

        # Set up OpenGL state
        glViewport(0, 0, width, height)
        # ... rest of setup

    def _init_opengl_context(self):
        """Create offscreen OpenGL context using GLUT."""
        from OpenGL.GLUT import glutInit, glutCreateWindow, glutHideWindow
        glutInit()
        self.glut_window = glutCreateWindow(b"Shader Renderer")
        glutHideWindow()  # Hidden window
```

### 4. Controller Simplified

**`menu/controller.py`**:
- Removed `_switch_to_opengl()` method (no longer needed)
- Simplified `_exit_shader_mode()` (no display mode switching)
- Just creates/destroys shader renderer, no display manipulation

```python
def _launch_shader_visualization(self, shader_path):
    # Just initialize shader renderer (handles its own OpenGL)
    self.shader_renderer = UnifiedShaderRenderer(self.width, self.height)
    self.shader_renderer.load_shader(shader_path)
    self.in_shader_mode = True

def _exit_shader_mode(self):
    # Just cleanup, no display mode changes
    self.shader_renderer = None
    self.in_shader_mode = False
```

## Rendering Flow

### Menu Mode

```
1. Menu renderer writes to Layer 0 (menu_layer)
2. Debug renderer writes to Layer 2 (debug_layer) if enabled
3. Display.show():
   a. Composites layers (menu + black + debug)
   b. PygameBackend.show() blits composited pixels
4. Result: Menu with FPS overlay on top
```

### Shader Mode

```
1. Shader renderer:
   a. Renders with OpenGL in hidden GLUT window
   b. Reads pixels back to numpy array
   c. Returns via read_pixels()
2. Pixels copied to Layer 1 (shader_layer)
3. Debug renderer writes to Layer 2 (debug_layer) if enabled
4. Display.show():
   a. Composites layers (black + shader + debug)
   b. PygameBackend.show() blits composited pixels
5. Result: Shader with FPS overlay on top
```

## Benefits

### 1. **FPS Overlay Works**
- Pygame always in regular mode → text rendering works
- Layer compositing works correctly
- No coordinate system issues

### 2. **Clean Abstraction**
- Display backend never exposed to controllers
- Shader renderer completely self-contained
- No OpenGL leakage outside shader renderer

### 3. **Simpler Code**
- No mode switching logic
- No OpenGL vs 2D rendering paths
- Single rendering method in display backend

### 4. **Better Separation**
- Shader rendering: handled by shader renderer (offscreen OpenGL)
- Display compositing: handled by display module (layer blending)
- Display output: handled by backend (pygame blitting)

## Testing

To verify the fix works:

1. **Start cube control**: `python cube_control.py --width 64 --height 64`
2. **Enable debug UI**: Navigate to SETTINGS → DEBUG UI → Toggle ON
3. **Test menu**: Should see "FPS XX.X" in top-left corner ✓
4. **Test shader**: Navigate to VISUALIZE → select shader → should see FPS on top of shader ✓
5. **Test switching**: Press ESC → FPS should continue working in menu ✓

## Technical Details

### GLUT Hidden Window

The shader renderer uses GLUT to create a hidden OpenGL window:

```python
glutInit()                          # Initialize GLUT
glutInitDisplayMode(GLUT_RGBA)      # Configure display mode
window = glutCreateWindow(b"...")   # Create window
glutHideWindow()                     # Hide it immediately
```

This provides:
- Full OpenGL 2.1+ context for shader rendering
- No visible window (hidden)
- Independent of main pygame window
- Works on macOS, Linux, Windows

### Pixel Readback

Shader renderer reads pixels from OpenGL framebuffer:

```python
pixel_data = glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)
frame = np.frombuffer(pixel_data, dtype=np.uint8)
frame = frame.reshape((height, width, 3))
frame = np.flip(frame, axis=0)  # Flip Y for correct orientation
return frame
```

This numpy array is then:
1. Copied to `shader_layer`
2. Composited with other layers
3. Blitted to pygame window

### No Performance Impact

- OpenGL rendering is offscreen (same cost as before)
- Pixel readback happens once per frame (same as before)
- Pygame blitting is efficient (standard path)
- No additional overhead from mode switching

## Related Documentation

- `DISPLAY_ARCHITECTURE.md` - Display module design
- `THREE_LAYER_ARCHITECTURE.md` - Layer compositing
- `FPS_OVERLAY_FIX.md` - Previous FPS fix attempt (superseded)
