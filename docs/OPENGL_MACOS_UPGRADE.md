# macOS OpenGL Version Upgrade Considerations

## Current State (December 2025)

### Working Configuration
- **Raspberry Pi 5**: OpenGL ES 3.0 / GLSL ES 3.00 (via EGL)
- **macOS**: OpenGL 2.1 / GLSL 1.20 (via GLUT)

Both platforms compile and render shaders successfully with this configuration.

### Why Current State Works
The shader compiler (`shader_compiler.py`) intelligently adapts to each platform:
- Detects legacy vs modern GLSL versions
- Conditionally includes helper functions (`tanh`, `round`) for legacy versions
- Handles `attribute`/`varying` vs `in`/`out` keywords
- Manages `gl_FragColor` vs explicit output declarations

## Why Upgrade macOS OpenGL?

### Benefits
1. **Unified shader code**: Both platforms would use modern GLSL 3.x syntax
2. **Better performance**: More efficient drivers and GPU utilization
3. **Modern features**: Access to geometry shaders, compute shaders, etc.
4. **Simpler maintenance**: Single GLSL version path instead of dual legacy/modern paths

### Current Limitations
- GLUT on macOS doesn't support requesting Core Profile contexts
- `glutInitContextVersion()` and `glutInitContextProfile()` are not available
- macOS defaults to OpenGL 2.1 compatibility mode without explicit hints

## Upgrade Options

### Option 1: GLFW (Recommended)

GLFW has proper Core Profile support on macOS and is the most reliable option for modern OpenGL.

#### Implementation

```python
import glfw
from OpenGL.GL import *

class GLFWShaderRenderer(ShaderRendererBase):
    """GLFW-based shader renderer with OpenGL 3.3+ Core Profile support."""

    def __init__(self, width: int, height: int):
        self.window = None
        super().__init__(width, height, scale=1)

    def _init_context(self):
        """Initialize GLFW with OpenGL 3.3 Core Profile."""
        if not glfw.init():
            raise RuntimeError("Failed to initialize GLFW")

        # Request OpenGL 3.3 Core Profile
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)  # Required on macOS

        # Create hidden offscreen window
        glfw.window_hint(glfw.VISIBLE, False)

        self.window = glfw.create_window(self.width, self.height, "Shader Renderer", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Failed to create GLFW window")

        glfw.make_context_current(self.window)

        # Query actual OpenGL version
        gl_version = glGetString(GL_VERSION)
        glsl_version = glGetString(GL_SHADING_LANGUAGE_VERSION)
        print(f"Created offscreen OpenGL context via GLFW")
        print(f"OpenGL Version: {gl_version.decode()}")
        print(f"GLSL Version: {glsl_version.decode()}")

    def _get_glsl_version(self) -> str:
        """Use OpenGL 3.3 Core Profile GLSL."""
        return "330 core"

    def _get_attribute_keyword(self) -> str:
        """Use modern 'in' keyword."""
        return "in"

    def _get_precision_statement(self) -> str:
        """Desktop GLSL doesn't require precision qualifiers."""
        return ""

    def cleanup(self):
        """Clean up GLFW resources."""
        self.uniform_manager.cleanup()

        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()

        if self.window:
            glfw.destroy_window(self.window)
            glfw.terminate()
```

#### Dependencies
```bash
pip install glfw
```

#### Pros
- ✅ Clean, modern API
- ✅ Proper Core Profile support on macOS
- ✅ Well-maintained and widely used
- ✅ Small, focused library

#### Cons
- ❌ New dependency to install
- ❌ Need to update platform detection in `shader_renderer.py`

### Option 2: Pygame with OpenGL Hints

Use pygame's OpenGL attribute setting before creating the window.

#### Implementation

```python
import pygame
from OpenGL.GL import *

class PygameOffscreenShaderRenderer(ShaderRendererBase):
    """Pygame-based offscreen renderer with Core Profile support."""

    def __init__(self, width: int, height: int):
        super().__init__(width, height, scale=1)

    def _init_context(self):
        """Initialize pygame with OpenGL 3.3 Core Profile."""
        pygame.init()

        # Request OpenGL 3.3 Core Profile
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                        pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, True)

        # Create hidden window for offscreen rendering
        flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN
        self.surface = pygame.display.set_mode((self.width, self.height), flags)

        # Query actual OpenGL version
        gl_version = glGetString(GL_VERSION)
        glsl_version = glGetString(GL_SHADING_LANGUAGE_VERSION)
        print(f"Created offscreen OpenGL context via pygame")
        print(f"OpenGL Version: {gl_version.decode()}")
        print(f"GLSL Version: {glsl_version.decode()}")
```

#### Pros
- ✅ Already have pygame as a dependency
- ✅ No new dependencies needed

#### Cons
- ❌ May conflict with existing pygame display windows
- ❌ pygame's OpenGL support is secondary to its 2D rendering focus
- ❌ Multiple pygame windows can be tricky

### Option 3: Stay with Current Implementation

Keep GLSL 120 on macOS and GLSL ES 3.00 on Raspberry Pi.

#### Pros
- ✅ Already working on both platforms
- ✅ No additional dependencies
- ✅ No risk of breaking existing code
- ✅ Shader compiler handles version differences automatically

#### Cons
- ❌ Maintains two different GLSL code paths
- ❌ Missing out on modern OpenGL features on macOS
- ❌ Slightly more complex shader compiler logic

## Recommendation

### Short-term: Option 3 (Current Implementation)
Since you have a working system now, keep the current implementation. The shader compiler already handles the differences elegantly, and you're not blocked on any features.

### Long-term: Option 1 (GLFW)
When you need modern OpenGL features or want to simplify the codebase:
1. Add GLFW as an optional dependency
2. Create `GLFWShaderRenderer` as an alternative to `GLUTShaderRenderer`
3. Add a configuration option or environment variable to choose which renderer to use
4. Keep GLUT as a fallback for systems without GLFW

## Implementation Plan (Future)

If/when upgrading to GLFW:

1. **Add GLFW dependency**
   ```bash
   pip install glfw
   ```

2. **Create new renderer**: `src/cube/shader/shader_renderer_glfw.py`

3. **Update platform detection** in `shader_renderer.py`:
   ```python
   def create_shader_renderer(width: int, height: int, **kwargs):
       system = platform.system()

       if system == 'Darwin':
           # Try GLFW first (modern OpenGL), fallback to GLUT (legacy)
           try:
               import glfw
               from .shader_renderer_glfw import GLFWShaderRenderer
               print("Using GLFW renderer (OpenGL 3.3 Core)")
               return GLFWShaderRenderer(width, height)
           except ImportError:
               from .shader_renderer_glut import GLUTShaderRenderer
               print("Using GLUT renderer (OpenGL 2.1 legacy)")
               return GLUTShaderRenderer(width, height)

       elif system == 'Linux':
           from .shader_renderer_egl import EGLShaderRenderer
           return EGLShaderRenderer(width, height)
   ```

4. **Update GLSL version**:
   - macOS: `#version 330 core` (instead of `#version 120`)
   - Raspberry Pi: `#version 300 es` (no change)

5. **Test thoroughly**:
   - Verify all existing shaders compile on both platforms
   - Check performance improvements
   - Ensure backward compatibility with GLUT fallback

## Related Resources

- [Stack Overflow: Why is my OpenGL version always 2.1 on Mac OS X?](https://stackoverflow.com/questions/19658745/why-is-my-opengl-version-always-2-1-on-mac-os-x)
- [GLFW Documentation](https://www.glfw.org/documentation.html)
- [Apple OpenGL Programming Guide](https://developer.apple.com/library/archive/documentation/GraphicsImaging/Conceptual/OpenGL-MacProgGuide/)
- [OpenGL ES 3.0 Specification](https://www.khronos.org/registry/OpenGL/specs/es/3.0/es_spec_3.0.pdf)

## Files Modified in Current Implementation

- `src/cube/shader/shader_compiler.py` - Smart version detection and polyfills
- `src/cube/shader/shader_renderer_egl.py` - OpenGL ES 3.0 context for Raspberry Pi
- `src/cube/shader/shader_renderer_glut.py` - OpenGL 2.1 legacy for macOS
- `src/cube/shader/shader_renderer_base.py` - Base class with version hooks

## Testing Status

| Platform | OpenGL Version | GLSL Version | Status | Date |
|----------|----------------|--------------|--------|------|
| macOS (GLUT) | 2.1 Metal | #version 120 | ✅ Working | 2025-12-03 |
| Raspberry Pi 5 (EGL) | ES 3.0 | #version 300 es | ✅ Working | 2025-12-03 |
