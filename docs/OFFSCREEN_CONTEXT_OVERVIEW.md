# Shared Offscreen Context - Overview & Considerations

## What Would It Entail?

Creating a shared offscreen OpenGL context for background shader validation involves:

### 1. Context Creation (Main Thread)
```python
# Must happen on main thread (platform requirement on macOS)
validation_context = create_offscreen_context()
```

### 2. Context Usage (Background Thread)
```python
# Make context current before OpenGL calls
make_context_current(validation_context)
test_shader_compilation(shader_path)  # Now safe!
release_context()
```

### 3. Thread Synchronization
```python
# Lock to prevent concurrent context operations
with context_lock:
    make_context_current(validation_context)
    # ... OpenGL operations
    release_context()
```

### 4. Cleanup (Application Exit)
```python
# Destroy context on proper thread
destroy_context(validation_context)
```

## Key Considerations

### 1. Platform Differences

| Platform | Recommended | Alternative | Notes |
|----------|-------------|-------------|-------|
| **macOS** | GLUT | CGL (native) | Context must be created on main thread |
| **Linux Desktop** | GLUT | GLX, EGL | EGL better for headless |
| **Raspberry Pi** | EGL | GLUT | EGL required for headless, needs GBM |
| **Windows** | GLUT | WGL (native) | GLUT most portable |

### 2. Thread Safety

**Critical Rules:**
```python
✅ DO: Create context on main thread (especially macOS)
✅ DO: Make context current before any OpenGL call
✅ DO: Release context after use
✅ DO: Use locks for context switching
❌ DON'T: Share context across threads simultaneously
❌ DON'T: Access OpenGL without making context current
❌ DON'T: Create contexts on background threads (macOS)
```

### 3. Context Creation Location

**macOS Requirement:**
```python
# MUST be on main thread
def __init__(self):  # Called during app initialization
    self.validation_context = create_glut_context()  ✅

# CRASHES on macOS
def _generate_shader_async(self):  # Background thread
    self.validation_context = create_glut_context()  ❌
```

**Why?** macOS Core Graphics requires window/context creation on main thread.

### 4. Resource Sharing vs Context Sharing

**Context Sharing (What we want):**
```python
# Two separate contexts that can share GPU resources
main_context = create_context()
shared_context = create_context(share_with=main_context)

# Can share: textures, buffers, shader programs
# Cannot share: VAOs, FBOs (in some implementations)
```

**Important:** We don't need to share resources for validation, just need any valid context.

### 5. Minimal Context Requirements

For shader validation, we need:
```python
# Absolute minimum
- OpenGL context ✅
- Ability to compile shaders ✅
- Don't need:
  - Window/surface ❌
  - Framebuffer ❌
  - Texture support ❌
  - Large dimensions ❌
```

**Optimization:** Create 1x1 pbuffer/offscreen context
```python
glutInitWindowSize(1, 1)  # Minimal overhead
```

### 6. Context Lifetime

**Option A: Long-lived (Recommended)**
```python
class ShaderAgent:
    def __init__(self):
        self.validation_context = create_context()  # Create once

    def validate(self):
        use_context(self.validation_context)  # Reuse

    def cleanup(self):
        destroy_context(self.validation_context)  # Cleanup once
```

**Option B: Per-validation**
```python
def validate(self):
    context = create_context()  # Create
    use_context(context)
    destroy_context(context)  # Destroy

# ❌ Slower, more overhead
```

### 7. Error Recovery

**Context can fail or be lost:**
```python
def validate_with_retry(self, shader_path):
    try:
        self.validation_context.make_current()
        return test_shader_compilation(shader_path)
    except ContextLostError:
        # Try recreating context
        self.validation_context = create_context()
        self.validation_context.make_current()
        return test_shader_compilation(shader_path)
    except Exception:
        # Give up on validation
        return False, "Validation unavailable"
```

### 8. Memory Management

**GPU resources need cleanup:**
```python
def _test_shader_compilation(self, shader_path):
    self.validation_context.make_current()

    try:
        vertex_shader = compileShader(...)
        fragment_shader = compileShader(...)
        program = compileProgram(...)

        # CRITICAL: Always cleanup
        glDeleteProgram(program)
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)

        return False, "Success"

    except Exception as e:
        # Cleanup might have failed - force flush
        glGetError()  # Clear error state
        return True, str(e)
```

### 9. Headless Environments

**Problem:** SSH sessions, Docker, CI/CD have no display

**EGL Solution (Linux):**
```python
# Works without X11 or Wayland
display = eglGetDisplay(EGL_DEFAULT_DISPLAY)
# Uses DRM/GBM for GPU access
```

**GLUT Solution (requires X):**
```python
# Needs Xvfb (virtual framebuffer)
Xvfb :99 -screen 0 1x1x24 &
export DISPLAY=:99
python cube_control.py
```

**Detection:**
```python
def is_headless():
    """Check if running headless."""
    if sys.platform == 'linux':
        return 'DISPLAY' not in os.environ
    return False

if is_headless():
    use_egl_context()
else:
    use_glut_context()
```

### 10. Existing Infrastructure

**Good news:** You already have offscreen renderers!

```python
# src/cube/shader/shader_renderer_glut.py
class GLUTShaderRenderer:
    def _init_context(self):
        """Already implements offscreen GLUT context!"""
        glutInit()
        glutInitWindowSize(width, height)
        window = glutCreateWindow(b"Shader Renderer")
        glutHideWindow()

# src/cube/shader/shader_renderer_egl.py
class EGLShaderRenderer:
    def _init_context(self):
        """Already implements headless EGL context!"""
        # ... EGL initialization with pbuffer
```

**Can reuse this code!** Just need to:
1. Extract context creation into standalone function
2. Make it reusable by agent
3. Add thread-safe context switching

## Implementation Complexity Assessment

### Low Complexity (1-2 days) ⭐⭐
**Extract existing GLUT context creation:**
- Copy code from `GLUTShaderRenderer._init_context()`
- Create `ValidationContextManager` wrapper
- Add to `ShaderAgent`
- Test on macOS

### Medium Complexity (3-4 days) ⭐⭐⭐
**Add platform detection:**
- GLUT for macOS/Windows
- EGL for Linux/Raspberry Pi
- Graceful fallback
- Test on all platforms

### High Complexity (5-8 days) ⭐⭐⭐⭐
**Full production-ready:**
- All platforms
- Context pooling
- Error recovery
- Performance optimization
- Comprehensive testing
- Documentation

## Recommendation Matrix

| Scenario | Recommended Approach | Complexity | Time |
|----------|---------------------|------------|------|
| **Prototype/Testing** | Skip validation | ⭐ | 0 days (current) |
| **macOS Only** | GLUT offscreen context | ⭐⭐ | 1-2 days |
| **Cross-Platform** | GLUT + EGL with detection | ⭐⭐⭐ | 3-4 days |
| **Production** | Full implementation + testing | ⭐⭐⭐⭐ | 5-8 days |

## Quick Start: Minimal Implementation

If you want to implement this quickly for testing:

```python
# src/cube/shader/validation_context.py (minimal version)

from OpenGL.GLUT import *
import threading

class SimpleValidationContext:
    def __init__(self):
        try:
            glutInit()
            glutInitDisplayMode(GLUT_RGBA)
            glutInitWindowSize(1, 1)
            self.window = glutCreateWindow(b"Validate")
            glutHideWindow()
            self.lock = threading.Lock()
            print("✓ Validation context ready")
        except Exception as e:
            print(f"✗ Validation context failed: {e}")
            self.window = None

    def make_current(self):
        if not self.window:
            return False
        with self.lock:
            glutSetWindow(self.window)
            return True

    def release(self):
        pass  # GLUT context stays current

# Usage in ShaderAgent
def __init__(self):
    self.val_ctx = SimpleValidationContext()

def _test_shader_compilation(self, shader_path):
    if not self.val_ctx.make_current():
        return False, "No context"

    return test_shader_compilation(shader_path)
```

**Testing:**
```bash
# Should work on macOS
python cube_control.py

# Should show: "✓ Validation context ready"
# Should enable automatic error retry
```

This gets you 80% of the benefit with 20% of the complexity!

## Conclusion

**Yes, we can create a shared offscreen context!**

**What it entails:**
- Extract existing GLUT/EGL context code
- Wrap in thread-safe manager
- Integrate with shader agent
- Handle platform differences
- Add proper cleanup

**Key considerations:**
1. ⚠️ **macOS:** Context must be created on main thread
2. ⚠️ **Thread safety:** Lock context operations
3. ⚠️ **Graceful fallback:** Skip validation if context fails
4. ⚠️ **Platform detection:** Choose GLUT vs EGL appropriately
5. ⚠️ **Memory cleanup:** Delete shaders/programs after validation
6. ⚠️ **Error handling:** Context creation can fail
7. ⚠️ **Testing:** Requires testing on all target platforms

**Effort:** 1-8 days depending on scope

**Benefit:** Automatic compilation error detection and retry during generation

**Risk:** Low to medium (can fallback to current behavior)

**Recommendation:** Start with minimal GLUT implementation for macOS, add EGL for Linux if needed.
