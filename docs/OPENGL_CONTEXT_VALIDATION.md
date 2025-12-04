# OpenGL Context Validation - Segfault Fix

## Problem

The application was crashing with a segmentation fault when the shader agent tried to validate shaders:

```
Testing shader compilation: cube_gently.glsl
zsh: segmentation fault  python cube_control.py ...
```

## Root Cause

The shader validation code was trying to compile shaders using OpenGL, but:

1. **Main thread**: Has an active OpenGL context (pygame window)
2. **Background thread**: NO OpenGL context (where shader generation happens)
3. **OpenGL contexts are thread-local**: Cannot be used from different threads

When `test_shader_compilation()` was called from the background thread, it attempted to use OpenGL functions without a context, causing a segmentation fault.

## Solution

Added OpenGL context checking before attempting shader compilation:

### Modified: src/cube/shader/shader_compiler.py

**Added context check** (lines 139-149):
```python
# Check if we have an active OpenGL context
try:
    # Try to get the current context - this will fail if no context exists
    from OpenGL.GL import glGetString, GL_VERSION
    version = glGetString(GL_VERSION)
    if version is None:
        # No active context
        return False, "No active OpenGL context - skipping validation"
except Exception:
    # No context available
    return False, "No active OpenGL context - skipping validation"
```

This check is added to both:
- `test_shader_compilation()`
- `test_shader_source_compilation()`

## Behavior

### Before Fix
```
Main Thread: Has OpenGL context ✅
Background Thread: No context ❌
  → Calls test_shader_compilation()
  → OpenGL functions crash
  → Segmentation fault 💥
```

### After Fix
```
Main Thread: Has OpenGL context ✅
Background Thread: No context ❌
  → Calls test_shader_compilation()
  → Context check detects no context
  → Returns (False, "No active OpenGL context - skipping validation")
  → Validation skipped safely ✅
  → Shader generation continues
  → Shader validated when loaded by renderer (in main thread)
```

## Validation Strategy

### Option 1: Skip validation in background thread (CURRENT)
**Pros**:
- ✅ No segfaults
- ✅ Simple and safe
- ✅ Shader still validated when loaded by renderer
- ✅ No complex threading issues

**Cons**:
- ❌ Compilation errors not detected until render time
- ❌ No automatic retry on compilation errors
- ❌ User has to manually report errors for retry

### Option 2: Create shared offscreen context (FUTURE)
**Pros**:
- ✅ Validate in background thread
- ✅ Automatic error retry
- ✅ Better user experience

**Cons**:
- ❌ Complex to implement
- ❌ Platform-specific code needed
- ❌ Requires EGL or similar for offscreen contexts
- ❌ More failure modes

### Option 3: Move validation to main thread (FUTURE)
**Pros**:
- ✅ Can use existing OpenGL context
- ✅ Automatic error retry
- ✅ Cross-platform

**Cons**:
- ❌ Main thread must check for completed generations
- ❌ Adds complexity to main loop
- ❌ Potential frame drops during compilation

## Current Implementation

For now, we use **Option 1**: Skip validation when no context is available.

### Workflow

```
User: "generate a rotating cube"
  ↓
[Background Thread]
  ├─ Generate shader with Claude ✅
  ├─ Try to validate compilation
  ├─ Detect: No OpenGL context
  ├─ Skip validation (return success)
  └─ Return shader to main thread
  ↓
[Main Thread]
  ├─ Receive shader result
  ├─ Attempt to load shader
  ├─ Has OpenGL context ✅
  ├─ Shader compilation happens here
  ├─ If error: Display to user
  └─ If success: Show visualization
```

### Error Handling

**Compilation errors are caught at render time:**

```python
try:
    renderer.load_shader(shader_path)
    # Launch visualization
except RuntimeError as e:
    # Show error to user
    print(f"Shader compilation failed: {e}")
    # User can then ask agent to fix it
```

## Testing

The fix prevents the segfault:

```bash
✅ No segfault when validating from background thread
✅ Gracefully skips validation when no context
✅ Shader still validated when loaded by renderer
✅ Compilation errors shown to user at render time
```

## Future Improvements

### Create Shared Offscreen Context

To enable background validation, we could create a shared offscreen OpenGL context:

```python
# Platform-specific offscreen context creation
import glfw  # or EGL for Linux

def create_offscreen_context():
    """Create an offscreen OpenGL context for shader validation."""
    if sys.platform == 'darwin':
        # macOS - use GLFW offscreen
        glfw.init()
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        window = glfw.create_window(1, 1, "offscreen", None, shared_with_main_window)
        glfw.make_context_current(window)
    elif sys.platform == 'linux':
        # Linux - use EGL
        from OpenGL.EGL import ...
        # Create EGL context
    return context

# Use in shader agent
if hasattr(self, 'validation_context'):
    # Make context current in background thread
    make_context_current(self.validation_context)
    # Now validation works!
    has_errors, output = test_shader_compilation(shader_path)
```

This is more complex but would enable the full validation workflow with automatic error retry.

## Related Files

- **src/cube/shader/shader_compiler.py**: Context checking added
- **src/cube/ai/shader_agent.py**: Uses test_shader_compilation()
- **src/cube/shader/shader_renderer_base.py**: Actual rendering with context

## Migration Notes

**No API changes**: The functions work the same way, they just gracefully skip validation when there's no OpenGL context instead of crashing.

**Backwards compatible**: ✅ Fully compatible
- Existing code continues to work
- No changes needed in calling code
- Validation still happens (just at a different time)

## Summary

- ✅ **Fixed**: Segmentation fault when validating from background thread
- ✅ **Safe**: Graceful context checking prevents crashes
- ✅ **Validated**: Shaders still validated (at render time instead of generation time)
- ⚠️ **Trade-off**: Compilation errors not detected until render, not during generation
- 🔮 **Future**: Can add offscreen context for background validation if needed
