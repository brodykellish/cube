# Shared Offscreen Context - Implementation Guide

## Concrete Implementation Using Existing Infrastructure

This guide shows how to implement a shared offscreen OpenGL context for the shader agent using your existing `GLUTShaderRenderer` and `EGLShaderRenderer` code.

## Architecture Overview

```
Main Thread                          Background Thread
-----------                          -----------------
┌─────────────────┐                 ┌─────────────────┐
│ Pygame Context  │                 │ GLUT Context    │
│ (Main Window)   │                 │ (Offscreen)     │
│                 │                 │                 │
│ - UI Rendering  │                 │ - Shader Test   │
│ - Visualization │                 │ - Compilation   │
│ - User Input    │ <───────────────│ - Validation    │
└─────────────────┘  Results/Actions└─────────────────┘
```

## Step-by-Step Implementation

### Step 1: Create Validation Context Manager

**New File:** `src/cube/shader/validation_context.py`

```python
"""
OpenGL context manager for shader validation in background threads.
"""

import sys
import threading
from typing import Optional
from pathlib import Path


class ValidationContextManager:
    """
    Manages an offscreen OpenGL context for shader validation.

    This allows shader compilation testing from background threads
    without interfering with the main rendering context.
    """

    def __init__(self):
        """Initialize validation context manager."""
        self.context = None
        self.context_type = None  # 'glut', 'egl', or None
        self.lock = threading.Lock()  # For thread-safe context operations
        self._init_context()

    def _init_context(self):
        """Initialize platform-appropriate offscreen context."""
        try:
            if sys.platform == 'darwin':
                self._init_glut_context()
            elif sys.platform == 'linux':
                # Try EGL first (headless), fallback to GLUT
                try:
                    self._init_egl_context()
                except Exception as e:
                    print(f"EGL context failed ({e}), trying GLUT...")
                    self._init_glut_context()
            else:
                # Windows or other
                self._init_glut_context()
        except Exception as e:
            print(f"Could not create validation context: {e}")
            print("Shader validation will be disabled")
            self.context = None

    def _init_glut_context(self):
        """Create GLUT offscreen context."""
        from OpenGL.GLUT import (
            glutInit, glutInitDisplayMode, glutInitWindowSize,
            glutCreateWindow, glutHideWindow,
            GLUT_RGBA, GLUT_DOUBLE
        )

        try:
            glutInit()
        except:
            pass  # Already initialized

        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE)
        glutInitWindowSize(1, 1)  # Minimal window
        window = glutCreateWindow(b"ShaderValidation")
        glutHideWindow()

        self.context = window
        self.context_type = 'glut'
        print("Validation context created: GLUT (offscreen)")

    def _init_egl_context(self):
        """Create EGL offscreen context (Linux/RPi)."""
        from OpenGL import EGL
        from ctypes import pointer, c_int

        # Get display
        display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
        if display == EGL.EGL_NO_DISPLAY:
            raise RuntimeError("Could not get EGL display")

        # Initialize
        major = c_int()
        minor = c_int()
        if not EGL.eglInitialize(display, pointer(major), pointer(minor)):
            raise RuntimeError("Could not initialize EGL")

        # Choose config
        config_attribs = [
            EGL.EGL_RENDERABLE_TYPE, EGL.EGL_OPENGL_ES2_BIT,
            EGL.EGL_SURFACE_TYPE, EGL.EGL_PBUFFER_BIT,
            EGL.EGL_BLUE_SIZE, 8,
            EGL.EGL_GREEN_SIZE, 8,
            EGL.EGL_RED_SIZE, 8,
            EGL.EGL_NONE
        ]

        configs = (EGL.EGLConfig * 1)()
        num_configs = c_int()

        if not EGL.eglChooseConfig(
            display,
            (c_int * len(config_attribs))(*config_attribs),
            configs,
            1,
            pointer(num_configs)
        ):
            raise RuntimeError("Could not choose EGL config")

        if num_configs.value == 0:
            raise RuntimeError("No suitable EGL configs")

        # Bind API
        if not EGL.eglBindAPI(EGL.EGL_OPENGL_ES_API):
            raise RuntimeError("Could not bind OpenGL ES API")

        # Create pbuffer surface (offscreen)
        pbuffer_attribs = [
            EGL.EGL_WIDTH, 1,
            EGL.EGL_HEIGHT, 1,
            EGL.EGL_NONE
        ]
        surface = EGL.eglCreatePbufferSurface(
            display,
            configs[0],
            (c_int * len(pbuffer_attribs))(*pbuffer_attribs)
        )

        if surface == EGL.EGL_NO_SURFACE:
            raise RuntimeError("Could not create pbuffer surface")

        # Create context
        context_attribs = [
            EGL.EGL_CONTEXT_CLIENT_VERSION, 2,
            EGL.EGL_NONE
        ]
        context = EGL.eglCreateContext(
            display,
            configs[0],
            EGL.EGL_NO_CONTEXT,
            (c_int * len(context_attribs))(*context_attribs)
        )

        if context == EGL.EGL_NO_CONTEXT:
            raise RuntimeError("Could not create EGL context")

        self.context = {
            'display': display,
            'surface': surface,
            'context': context
        }
        self.context_type = 'egl'
        print("Validation context created: EGL (headless)")

    def make_current(self) -> bool:
        """
        Make validation context current for the calling thread.

        Returns:
            True if context made current, False otherwise
        """
        if not self.context:
            return False

        with self.lock:
            try:
                if self.context_type == 'glut':
                    from OpenGL.GLUT import glutSetWindow
                    glutSetWindow(self.context)
                    return True

                elif self.context_type == 'egl':
                    from OpenGL import EGL
                    ctx = self.context
                    result = EGL.eglMakeCurrent(
                        ctx['display'],
                        ctx['surface'],
                        ctx['surface'],
                        ctx['context']
                    )
                    return bool(result)

            except Exception as e:
                print(f"Error making validation context current: {e}")
                return False

        return False

    def release(self):
        """Release the current context."""
        try:
            if self.context_type == 'egl':
                from OpenGL import EGL
                EGL.eglMakeCurrent(
                    self.context['display'],
                    EGL.EGL_NO_SURFACE,
                    EGL.EGL_NO_SURFACE,
                    EGL.EGL_NO_CONTEXT
                )
        except:
            pass

    def is_available(self) -> bool:
        """Check if validation context is available."""
        return self.context is not None

    def cleanup(self):
        """Clean up validation context."""
        if not self.context:
            return

        with self.lock:
            try:
                if self.context_type == 'glut':
                    from OpenGL.GLUT import glutDestroyWindow
                    glutDestroyWindow(self.context)

                elif self.context_type == 'egl':
                    from OpenGL import EGL
                    ctx = self.context
                    EGL.eglDestroyContext(ctx['display'], ctx['context'])
                    EGL.eglDestroySurface(ctx['display'], ctx['surface'])
                    EGL.eglTerminate(ctx['display'])

                self.context = None
                print("Validation context cleaned up")

            except Exception as e:
                print(f"Error cleaning up validation context: {e}")
```

### Step 2: Integrate with ShaderAgent

**Modified:** `src/cube/ai/shader_agent.py`

```python
from cube.shader.validation_context import ValidationContextManager

class ShaderAgent:
    def __init__(self, shaders_dir: Path, examples_root: Optional[Path] = None):
        # ... existing init

        # Create validation context manager
        self.validation_ctx_manager = ValidationContextManager()

        if self.validation_ctx_manager.is_available():
            print("✓ Shader validation enabled (offscreen context)")
        else:
            print("⚠ Shader validation disabled (no offscreen context)")

    def _test_shader_compilation(self, shader_path: Path) -> Tuple[bool, str]:
        """Test shader compilation (now works in background thread)."""

        # Try to make validation context current
        if not self.validation_ctx_manager.make_current():
            # No context available - skip validation
            return False, "No validation context - skipping"

        try:
            # Now we have a context - test compilation
            from cube.shader.shader_compiler import test_shader_compilation
            has_errors, output = test_shader_compilation(shader_path)
            return has_errors, output

        finally:
            # Always release context when done
            self.validation_ctx_manager.release()

    def cleanup(self):
        """Clean up shader agent resources."""
        if hasattr(self, 'validation_ctx_manager'):
            self.validation_ctx_manager.cleanup()
```

### Step 3: Handle Context Creation Timing

**Problem:** GLUT requires initialization on main thread (macOS)

**Solution:** Create context during agent initialization (happens on main thread)

```python
# In controller.py (main thread)
shaders_dir = Path(__file__).parent.parent.parent / 'shaders'
self.menu_navigator.register_menu('prompt', PromptMenuState(
    self.width, self.height, shaders_dir
))

# PromptMenuState.__init__ calls ShaderAgent.__init__
# ShaderAgent creates validation context
# This all happens on main thread ✅
```

## Edge Cases & Gotchas

### 1. GLUT Already Initialized

```python
try:
    glutInit()
except RuntimeError:
    pass  # Already initialized - OK
```

### 2. Multiple Agents

```python
# If creating multiple agents, share the validation context
_global_validation_context = None

def get_validation_context():
    global _global_validation_context
    if _global_validation_context is None:
        _global_validation_context = ValidationContextManager()
    return _global_validation_context
```

### 3. Context Loss

```python
def _test_shader_compilation(self, shader_path):
    for attempt in range(2):  # Retry once
        if self.validation_ctx_manager.make_current():
            try:
                return test_shader_compilation(shader_path)
            except Exception as e:
                if "context" in str(e).lower() and attempt == 0:
                    # Context might be lost - try recreating
                    self.validation_ctx_manager = ValidationContextManager()
                    continue
                raise
        else:
            return False, "No context available"
```

### 4. GPU Memory

```python
# After validation, cleanup immediately
glDeleteProgram(program)
glDeleteShader(vertex_shader)
glDeleteShader(fragment_shader)

# Optional: Force cleanup
glFinish()  # Wait for operations to complete
```

### 5. Platform Detection

```python
import sys

def should_use_egl():
    """Determine if we should use EGL over GLUT."""
    if sys.platform != 'linux':
        return False

    # Check if running headless (no DISPLAY)
    if 'DISPLAY' not in os.environ:
        return True

    # Check if on Raspberry Pi
    if Path('/proc/device-tree/model').exists():
        model = Path('/proc/device-tree/model').read_text()
        if 'Raspberry Pi' in model:
            return True

    return False
```

## Benefits of Implementation

**Immediate:**
- ✅ Automatic error detection during generation
- ✅ Up to 3 automatic retry attempts
- ✅ No user intervention needed for common errors
- ✅ Better user experience

**Long-term:**
- ✅ Faster iteration cycles
- ✅ Higher quality generated shaders
- ✅ Less frustration for users
- ✅ Enables advanced validation (performance testing, etc.)

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Context creation fails | No validation | Graceful fallback to current behavior |
| Platform incompatibility | Validation unavailable | Platform detection + fallback |
| Thread synchronization bugs | Crashes or hangs | Careful locking, thorough testing |
| Memory leaks | GPU memory exhaustion | Proper cleanup after each validation |
| Performance overhead | Slower generation | Only use when needed, optimize context switching |

## Testing Plan

### Unit Tests
```python
def test_context_creation():
    """Test that context can be created."""
    ctx = ValidationContextManager()
    assert ctx.is_available()

def test_context_switching():
    """Test making context current from different thread."""
    ctx = ValidationContextManager()

    def bg_thread():
        assert ctx.make_current()
        # Verify context is current
        from OpenGL.GL import glGetString, GL_VERSION
        version = glGetString(GL_VERSION)
        assert version is not None
        ctx.release()

    thread = threading.Thread(target=bg_thread)
    thread.start()
    thread.join()

def test_shader_compilation_with_context():
    """Test actual shader compilation."""
    ctx = ValidationContextManager()
    ctx.make_current()

    # Test good shader
    shader_path = Path('shaders/primitives/sphere.glsl')
    has_errors, output = test_shader_compilation(shader_path)
    assert not has_errors

    # Test bad shader
    bad_shader = Path('test_bad.glsl')
    bad_shader.write_text('void mainImage() { invalid syntax')
    has_errors, output = test_shader_compilation(bad_shader)
    assert has_errors
    assert 'error' in output.lower()

    ctx.release()
```

### Integration Tests
```python
def test_background_validation():
    """Test validation from background thread (full workflow)."""
    agent = ShaderAgent(Path('shaders/generated'))

    # Should have validation context
    assert agent.validation_ctx_manager.is_available()

    # Test generation with validation
    result = agent.generate_shader_with_validation(
        "Create a red sphere"
    )

    # Should have validated and succeeded
    assert result.success
```

### Platform Tests
- macOS: GLUT context creation and validation
- Linux desktop: GLUT or EGL context
- Raspberry Pi: EGL context with GBM
- Windows: GLUT context

## Performance Considerations

### Context Switching Overhead

```python
# Measure overhead
import time

start = time.time()
for i in range(100):
    ctx.make_current()
    ctx.release()
end = time.time()

overhead_per_switch = (end - start) / 100
print(f"Context switch overhead: {overhead_per_switch*1000:.2f}ms")

# Typical: 0.1-1ms per switch (acceptable)
```

### Optimization: Context Pooling

```python
class ValidationContextPool:
    """Pool of validation contexts for parallel validation."""

    def __init__(self, size: int = 1):
        self.contexts = [ValidationContextManager() for _ in range(size)]
        self.available = queue.Queue()
        for ctx in self.contexts:
            self.available.put(ctx)

    def acquire(self) -> Optional[ValidationContextManager]:
        """Get an available context."""
        try:
            return self.available.get(timeout=10.0)
        except queue.Empty:
            return None

    def release(self, ctx: ValidationContextManager):
        """Return context to pool."""
        self.available.put(ctx)
```

## Debugging Tools

### Context Verification

```python
def verify_context():
    """Verify OpenGL context is properly initialized."""
    from OpenGL.GL import glGetString, GL_VERSION, GL_VENDOR, GL_RENDERER

    print("OpenGL Context Info:")
    print(f"  Version: {glGetString(GL_VERSION)}")
    print(f"  Vendor: {glGetString(GL_VENDOR)}")
    print(f"  Renderer: {glGetString(GL_RENDERER)}")

    # Test basic operation
    glClearColor(0, 0, 0, 1)
    glClear(GL_COLOR_BUFFER_BIT)

    error = glGetError()
    if error != GL_NO_ERROR:
        print(f"  Error: {error}")
    else:
        print("  ✓ Context working")
```

### Thread Safety Check

```python
import threading

def test_concurrent_validation():
    """Test multiple threads using validation contexts."""
    results = []

    def validate_shader(shader_idx):
        ctx = get_validation_context()
        ctx.make_current()
        # Validate...
        ctx.release()
        results.append(shader_idx)

    threads = [
        threading.Thread(target=validate_shader, args=(i,))
        for i in range(5)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5
    assert len(set(results)) == 5  # All unique
```

## Rollout Strategy

### Phase 1: Soft Launch (Experimental)
```python
# Add feature flag
ENABLE_SHADER_VALIDATION = os.environ.get('ENABLE_SHADER_VALIDATION', 'false').lower() == 'true'

if ENABLE_SHADER_VALIDATION:
    self.validation_ctx_manager = ValidationContextManager()
else:
    self.validation_ctx_manager = None
```

### Phase 2: Opt-Out
```python
# Default enabled, allow disabling
ENABLE_SHADER_VALIDATION = os.environ.get('ENABLE_SHADER_VALIDATION', 'true').lower() != 'false'
```

### Phase 3: Always On
```python
# Remove flag, always create context
self.validation_ctx_manager = ValidationContextManager()

# But still gracefully handle failures
if not self.validation_ctx_manager.is_available():
    print("Warning: Shader validation unavailable")
```

## Estimated Work

### Implementation (~2-3 hours)
- ✅ Create `ValidationContextManager` class
- ✅ Add GLUT context creation
- ✅ Add EGL context creation (copy from existing code)
- ✅ Integrate with `ShaderAgent`

### Testing (~2-3 hours)
- ✅ Test on macOS (GLUT)
- ✅ Test on Linux (EGL and GLUT)
- ⚠️ Test on Raspberry Pi (EGL with GBM)
- ✅ Test thread safety
- ✅ Test error cases

### Debugging (~1-2 hours)
- Platform-specific issues
- Context creation failures
- Thread synchronization issues

**Total: 5-8 hours of development work**

## Alternative: Validation on Demand

A simpler approach that doesn't require background contexts:

```python
def validate_shader_on_demand(self, shader_path: Path):
    """
    Validate shader when user explicitly loads it.

    This happens in main thread (has context).
    If errors, offer to fix automatically.
    """
    try:
        # Try to load shader (main thread has context)
        renderer.load_shader(shader_path)
        return True, "Success"
    except Exception as e:
        error_msg = str(e)

        # Offer automatic fix
        print(f"Shader compilation failed: {error_msg}")
        print("Automatically retrying with error feedback...")

        # Generate fix (background thread - no validation)
        result = self.generate_shader(
            f"Fix compilation errors in:\n```glsl\n{shader_path.read_text()}\n```",
            error_feedback=error_msg,
            prompt_type="error_fixing"
        )

        if result.success:
            # Try loading fixed shader
            try:
                renderer.load_shader(result.shader_path)
                return True, "Fixed and loaded"
            except Exception as e2:
                return False, f"Still broken: {e2}"

        return False, error_msg
```

**Pros:**
- ✅ Simple - no context management
- ✅ Works today with existing code
- ✅ Automatic error retry
- ✅ Main thread has context guaranteed

**Cons:**
- ❌ User sees error briefly
- ❌ Slower (must attempt render first)
- ❌ Less elegant

## Recommendation

**For production stability:** Use the simpler "validate on demand" approach

**For best UX:** Implement shared offscreen context with:
- Graceful fallback if creation fails
- Platform detection (GLUT for macOS, EGL for Linux)
- Proper thread locking
- Comprehensive testing

The infrastructure already exists (GLUT and EGL renderers), so the main work is creating a lightweight wrapper for validation-only contexts and integrating it with the agent's threading model.
