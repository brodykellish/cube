# Creating a Shared Offscreen OpenGL Context for Shader Validation

## Overview

Creating a shared offscreen OpenGL context would allow the shader agent to validate shader compilation in the background thread, enabling automatic error detection and retry. This document explores what this would entail, the considerations, and implementation approaches.

## Current Situation

**Main Thread:**
- Has pygame OpenGL context
- Renders UI and visualizations
- Can compile shaders ✅

**Background Thread (Shader Agent):**
- Generates shaders via Claude API
- NO OpenGL context
- Cannot compile shaders ❌
- Must skip validation

## What is Context Sharing?

OpenGL contexts can share resources (textures, buffers, shaders) but cannot be used across threads directly. However, you can create multiple contexts that **share resources** and use them in different threads.

```
Main Context (Main Thread)
  ├─ Can access: Own resources + Shared resources
  └─ Used for rendering

Shared Context (Background Thread)
  ├─ Can access: Own resources + Shared resources
  └─ Used for validation only
```

**Key Point:** Each thread needs its own context, but they can share GPU resources.

## Implementation Approaches

### Approach 1: GLUT Offscreen Context (macOS)

**Pros:**
- ✅ Already implemented (`GLUTShaderRenderer`)
- ✅ Cross-platform (works on macOS, Linux, Windows)
- ✅ Simple to use
- ✅ No X11 dependency

**Cons:**
- ❌ GLUT is somewhat outdated
- ❌ Creates hidden window (small overhead)
- ❌ May not work in completely headless environments

**Code Example:**
```python
from OpenGL.GLUT import *
import threading

class ShaderAgent:
    def __init__(self, ...):
        # Create validation context in main thread first
        self._init_validation_context()

    def _init_validation_context(self):
        """Initialize GLUT offscreen context for validation."""
        try:
            glutInit()
        except:
            pass

        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE)
        glutInitWindowSize(1, 1)  # Minimal size
        self.validation_window = glutCreateWindow(b"Validation")
        glutHideWindow()

        # Get the context handle (platform-specific)
        self.validation_context = self._get_current_context()
        print("Created validation context via GLUT")

    def _generate_shader_async(self, user_prompt: str):
        """Background thread worker."""
        # Make validation context current in this thread
        self._make_context_current(self.validation_context)

        # Now we can validate!
        result = agent.generate_shader(...)
        has_errors, output = test_shader_compilation(shader_path)

        if has_errors:
            # Retry with error feedback
            result = agent.generate_shader(error_feedback=output)
```

### Approach 2: EGL Context (Linux/Raspberry Pi)

**Pros:**
- ✅ Already implemented (`EGLShaderRenderer`)
- ✅ True headless operation
- ✅ No windowing system required
- ✅ Efficient for servers/embedded

**Cons:**
- ❌ Linux-only (no macOS/Windows)
- ❌ More complex setup
- ❌ Requires DRM/GBM on some systems

**Code Example:**
```python
from OpenGL import EGL
import os

class ShaderAgent:
    def _init_validation_context_egl(self):
        """Initialize EGL offscreen context for validation."""
        # Get display
        display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
        EGL.eglInitialize(display, None, None)

        # Choose config
        config_attribs = [
            EGL.EGL_RENDERABLE_TYPE, EGL.EGL_OPENGL_ES2_BIT,
            EGL.EGL_SURFACE_TYPE, EGL.EGL_PBUFFER_BIT,
            EGL.EGL_NONE
        ]
        configs = (EGL.EGLConfig * 1)()
        num_configs = c_int()
        EGL.eglChooseConfig(display, config_attribs, configs, 1, pointer(num_configs))

        # Create pbuffer surface (offscreen)
        pbuffer_attribs = [
            EGL.EGL_WIDTH, 1,
            EGL.EGL_HEIGHT, 1,
            EGL.EGL_NONE
        ]
        surface = EGL.eglCreatePbufferSurface(display, configs[0], pbuffer_attribs)

        # Create context
        context_attribs = [
            EGL.EGL_CONTEXT_CLIENT_VERSION, 2,
            EGL.EGL_NONE
        ]
        context = EGL.eglCreateContext(display, configs[0], EGL.EGL_NO_CONTEXT, context_attribs)

        self.validation_display = display
        self.validation_surface = surface
        self.validation_context = context

    def _make_validation_context_current(self):
        """Make validation context current in background thread."""
        EGL.eglMakeCurrent(
            self.validation_display,
            self.validation_surface,
            self.validation_surface,
            self.validation_context
        )
```

### Approach 3: Platform-Specific Native Contexts

**macOS (CGL):**
```python
from ctypes import *
from OpenGL.platform import darwin

# Create CGLContext
cgl = darwin.CGL
pixel_format = cgl.CGLChoosePixelFormat(...)
context = cgl.CGLCreateContext(pixel_format, share_context)
```

**Linux (GLX):**
```python
from OpenGL import GLX

# Create GLXContext
display = GLX.glXGetCurrentDisplay()
context = GLX.glXCreateContext(display, visual_info, share_context, True)
```

**Windows (WGL):**
```python
from OpenGL import WGL

# Create WGLContext
hdc = wgl.wglGetCurrentDC()
context = wgl.wglCreateContext(hdc)
wgl.wglShareLists(main_context, context)
```

## Key Considerations

### 1. Thread Safety

**Problem:** OpenGL contexts are NOT thread-safe
**Solution:** Each thread must make its context current before use

```python
def background_thread():
    # CRITICAL: Make context current first
    make_context_current(validation_context)

    # Now safe to use OpenGL
    has_errors, output = test_shader_compilation(shader_path)

    # Release context when done
    release_context()
```

### 2. Context Creation Location

**Problem:** Context creation may require main thread
**Solution:** Create context in main thread, use in background thread

```python
# In main thread (during initialization)
self.validation_context = create_offscreen_context()

# In background thread
def _generate_shader_async(self):
    make_context_current(self.validation_context)
    # ... validation code
```

### 3. Resource Sharing

**Problem:** Need to share uniforms, textures between contexts
**Solution:** Use shared contexts (created with `share_context` parameter)

```python
# When creating validation context, specify main context to share with
validation_context = create_context(share_with=main_context)
```

**What gets shared:**
- ✅ Shader programs
- ✅ Textures
- ✅ Buffers (VBO, FBO)
- ❌ VAOs (Vertex Array Objects) - not shared!
- ❌ Display lists (legacy)

### 4. Cleanup

**Problem:** Context cleanup must happen on correct thread
**Solution:** Clean up context on the thread that uses it

```python
def cleanup_validation_context(self):
    """Must be called from background thread or main thread."""
    if self.validation_context:
        make_context_current(self.validation_context)
        # Cleanup resources...
        destroy_context(self.validation_context)
```

### 5. Platform Differences

**macOS:**
- ✅ GLUT works well
- ✅ CGL native API available
- ⚠️ Must create contexts on main thread

**Linux:**
- ✅ EGL preferred for headless
- ✅ GLX for X11 systems
- ✅ Can create contexts on any thread

**Raspberry Pi:**
- ✅ EGL required
- ⚠️ May need GBM device for proper operation
- ⚠️ Limited resources (GPU memory)

### 6. Error Handling

**Context creation can fail:**
```python
try:
    context = create_offscreen_context()
except Exception as e:
    # Fallback: Skip validation
    print(f"Could not create validation context: {e}")
    context = None

# Later, check before use
if self.validation_context:
    validate_shader()
else:
    skip_validation()
```

### 7. Performance

**Context switching has overhead:**
```python
# Multiple switches (slower)
for shader in shaders:
    make_context_current(validation_context)
    validate(shader)
    release_context()

# Single switch (faster)
make_context_current(validation_context)
for shader in shaders:
    validate(shader)
release_context()
```

### 8. Debugging

**Context issues can be hard to debug:**
- Use `glGetError()` after each operation
- Check if context is current: `glGetString(GL_VERSION)`
- Log context switches
- Use OpenGL debug contexts on development

```python
# Enable debug output
glEnable(GL_DEBUG_OUTPUT)
glEnable(GL_DEBUG_OUTPUT_SYNCHRONOUS)
glDebugMessageCallback(debug_callback, None)
```

## Recommended Implementation

For this project, I recommend **Approach 1 (GLUT)** with platform detection:

```python
class ShaderAgent:
    def __init__(self, shaders_dir: Path, examples_root: Optional[Path] = None):
        # ... existing init

        # Try to create validation context
        self.validation_context = self._create_validation_context()
        self.validation_available = (self.validation_context is not None)

    def _create_validation_context(self):
        """Create offscreen context for shader validation."""
        import sys

        try:
            if sys.platform == 'darwin':
                # macOS - use GLUT
                return self._create_glut_context()
            elif sys.platform == 'linux':
                # Linux - try EGL, fallback to GLUT
                try:
                    return self._create_egl_context()
                except:
                    return self._create_glut_context()
            else:
                # Windows - use GLUT
                return self._create_glut_context()
        except Exception as e:
            print(f"Could not create validation context: {e}")
            print("Shader validation will be skipped")
            return None

    def _create_glut_context(self):
        """Create GLUT offscreen context."""
        from OpenGL.GLUT import *

        # Must be called from main thread!
        glutInit()
        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE)
        glutInitWindowSize(1, 1)
        window = glutCreateWindow(b"Validation")
        glutHideWindow()

        # Get context handle (platform-specific)
        # This is simplified - actual implementation would need platform checks
        return window  # Return window handle for now

    def _make_validation_context_current(self):
        """Make validation context current (from background thread)."""
        if not self.validation_context:
            return False

        # Platform-specific context switching
        # This is simplified - actual implementation would need platform checks
        from OpenGL.GLUT import glutSetWindow
        glutSetWindow(self.validation_context)
        return True

    def _test_shader_compilation(self, shader_path: Path) -> Tuple[bool, str]:
        """Test shader compilation (can now work in background thread)."""
        if not self.validation_available:
            # Fallback to skipping validation
            return False, "No validation context available - skipping"

        # Make validation context current
        if not self._make_validation_context_current():
            return False, "Could not activate validation context"

        # Now we can safely validate
        return test_shader_compilation(shader_path)
```

## Testing Strategy

1. **Unit Test:** Test context creation on main thread
2. **Thread Test:** Test context switching in background thread
3. **Validation Test:** Test actual shader compilation
4. **Failure Test:** Test graceful fallback when context unavailable

```python
def test_validation_context():
    """Test validation context creation and use."""
    agent = ShaderAgent(Path('shaders/generated'))

    # Test 1: Context created
    assert agent.validation_available, "Should create validation context"

    # Test 2: Can validate from background thread
    import threading
    result = [None]

    def bg_test():
        has_errors, output = agent._test_shader_compilation(test_shader)
        result[0] = (has_errors, output)

    thread = threading.Thread(target=bg_test)
    thread.start()
    thread.join()

    assert result[0] is not None, "Should complete validation"

    # Test 3: Graceful fallback if context fails
    agent.validation_context = None
    agent.validation_available = False
    has_errors, output = agent._test_shader_compilation(test_shader)
    assert not has_errors, "Should skip validation gracefully"
    assert "skipping" in output.lower()
```

## Migration Path

### Phase 1: Optional Validation Context (Safe)
```python
# Create context if possible, skip if not
validation_context = try_create_context()

if validation_context:
    validate_shader()  # With automatic retry
else:
    skip_validation()  # Current behavior
```

### Phase 2: Strongly Recommended
```python
# Warn if context not available
if not validation_context:
    print("WARNING: No validation context - errors won't be auto-fixed")
```

### Phase 3: Required (Future)
```python
# Require validation context
if not validation_context:
    raise RuntimeError("Validation context required")
```

## Estimated Complexity

**Implementation Time:** 1-2 days
**Testing Time:** 1 day
**Debugging Time:** 1-2 days (platform-specific issues)

**Total:** 3-5 days of work

## Recommended Next Steps

1. ✅ **Current:** Skip validation when no context (DONE)
2. ⏭️ **Next:** Add optional GLUT validation context
3. ⏭️ **Then:** Test on macOS, Linux, Raspberry Pi
4. ⏭️ **Finally:** Enable automatic error retry with validation

## Alternative: Simpler Approach

Instead of full context sharing, we could:

1. **Validate on first render:**
   - Generate shader in background
   - When user loads shader, validation happens naturally
   - If errors, show to user and offer to fix
   - Send errors back to agent for retry

2. **Pros:**
   - ✅ No context sharing complexity
   - ✅ Works today with current code
   - ✅ User sees shader attempt immediately

3. **Cons:**
   - ❌ User must manually trigger retry
   - ❌ Slower feedback loop
   - ❌ Less automatic

## Conclusion

Creating a shared offscreen context is **technically feasible** but requires:
- Platform-specific code
- Careful thread management
- Proper context switching
- Thorough testing

**Recommendation:** Start with the simpler "validate on render" approach, then add optional offscreen context if automatic retry is critical.

The infrastructure (GLUT and EGL renderers) already exists in the codebase, so the main work would be:
1. Adapting them for background thread use
2. Adding context switching logic
3. Platform-specific testing
4. Fallback handling
