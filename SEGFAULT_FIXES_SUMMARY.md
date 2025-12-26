# Segfault Fixes Summary

This document summarizes all changes made to reduce segfaults and crashes related to window management, fullscreen transitions, and OpenGL context handling.

## Overview

The application experienced segfaults and crashes primarily during:
- Fullscreen transitions
- Window close operations
- OpenGL resource cleanup
- Window resize events

These issues were caused by race conditions between the visualization render thread and the main thread, improper OpenGL context management, and lack of synchronization during window state changes.

## Changes Made

### 1. Fullscreen Transition Synchronization

**File**: `src/cube/display/pyglet_backend.py`

**Problem**: OpenGL/Metal operations during window resize caused segfaults and Metal command buffer errors (`failed assertion 'commit command buffer with uncommitted encoder'`).

**Solution**:
- Added `_fullscreen_transitioning` flag to track when fullscreen transitions are in progress
- Set flag to `True` at the start of both entering and exiting fullscreen
- Increased transition delay from 0.1s to 0.2s to allow in-flight OpenGL operations to complete
- Reset flag to `False` after transition completes
- Added error handling to reset flag if fullscreen operations fail

**Key Changes**:
```python
# Set flag before transition
self._fullscreen_transitioning = True
self.window.set_fullscreen(True)
time.sleep(0.2)  # Allow operations to complete
# ... update OpenGL resources ...
self._fullscreen_transitioning = False
```

### 2. Render Loop Protection During Transitions

**File**: `src/cube/render/visualization_runner.py`

**Problem**: Render loop continued executing during fullscreen transitions, causing OpenGL/Metal conflicts.

**Solution**:
- Added check in render loop to skip rendering when `_fullscreen_transitioning` is `True`
- Added small sleep (0.01s) during transitions to avoid busy-waiting
- Skip display operations during transitions

**Key Changes**:
```python
# Skip rendering during transitions
backend = self._viz_window.backend if self._viz_window else None
if backend and getattr(backend, '_fullscreen_transitioning', False):
    time.sleep(0.01)  # Avoid busy-waiting
    continue
```

### 3. Display Method Protection

**File**: `src/cube/display/pyglet_backend.py`

**Problem**: `display()` method was called during fullscreen transitions, causing Metal errors.

**Solution**:
- Early return in `display()` if `_fullscreen_transitioning` is `True`
- Added error handling for context switching
- Added validation checks before texture operations

**Key Changes**:
```python
def display(self, framebuffer: np.ndarray):
    # Skip display during fullscreen transitions
    if self._fullscreen_transitioning:
        return
    # ... rest of display logic ...
```

### 4. Texture Recreation Safety

**File**: `src/cube/display/pyglet_backend.py`

**Problem**: Texture recreation during resize caused `glGenTextures` invalid operation errors (GLError 1282).

**Solution**:
- Added `_fullscreen_transitioning` check before texture recreation
- Added error checking with `glGetError()` before critical OpenGL operations
- Added exception handling around texture creation/deletion
- Added validation to skip frames if texture creation fails
- Added context validation before texture operations

**Key Changes**:
```python
# Check if texture needs to be resized (but skip during fullscreen transition)
if not self._fullscreen_transitioning and (fb_width != self._width or fb_height != self._height):
    # Recreate texture with error handling
    try:
        self.texture = glGenTextures(1)
        error = glGetError()
        if error != GL_NO_ERROR:
            # Handle error gracefully
    except Exception as e:
        # Handle exception
```

### 5. OpenGL Cleanup Error Handling

**File**: `src/cube/display/pyglet_backend.py`

**Problem**: Cleanup attempted to delete invalid OpenGL resources, causing errors (GLError 1281 for programs).

**Solution**:
- Added context validation before cleanup
- Added error handling for each OpenGL resource deletion (VAO, VBO, texture, program)
- Suppressed expected `GL_INVALID_VALUE` (1281) errors for programs (may already be deleted)
- Added `finally` block to ensure window always closes
- Added checks to validate resources exist before deletion

**Key Changes**:
```python
def close(self):
    try:
        if hasattr(self, 'window') and self.window and not self.window.has_exit:
            self.window.switch_to()
            # Clear errors
            while glGetError() != GL_NO_ERROR:
                pass
            # Delete resources with error handling
            if self.program and self.program != 0:
                try:
                    glDeleteProgram(self.program)
                    error = glGetError()
                    if error != GL_NO_ERROR and error != 1281:  # Suppress expected errors
                        print(f"Error: {error}")
                except Exception as e:
                    print(f"Exception: {e}")
    finally:
        # Always close window
        if hasattr(self, 'window') and self.window:
            self.window.close()
```

### 6. Window Close Thread Safety

**Files**: 
- `src/cube/display/visualization_window.py`
- `src/cube/render/visualization_runner.py`
- `src/cube/controller.py`

**Problem**: ESC key tried to stop thread from within itself, causing "cannot join current thread" error.

**Solution**:
- Added `_close_requested` flag for thread-safe close requests
- Changed ESC handling to request close instead of calling stop callback
- Added `check_close_request()` method called from main thread
- Fixed cleanup to happen on main thread, not from visualization thread
- Added window state checks before accessing window properties

**Key Changes**:
```python
# In visualization_window.py
def close(self):
    """Request window close (thread-safe, actual close happens on main thread)."""
    self._close_requested = True
    self._has_exit = True

def check_close_request(self):
    """Check if close was requested and close window (must be called from main thread)."""
    if self._close_requested:
        self._close_requested = False
        self.backend.window.close()
        return True
    return False

# In visualization_runner.py
if self._viz_input_manager.is_action_pressed(Action.CANCEL):
    if self._viz_window:
        self._viz_window.close()  # Request close, don't stop thread
    self._stop_flag.set()
    return

# In controller.py
if self.viz_window:
    self.viz_window.poll()
    if self.viz_window.check_close_request():  # Main thread handles close
        self._cleanup_visualization()
```

### 7. Render Loop Error Handling

**File**: `src/cube/render/visualization_runner.py`

**Problem**: Render loop crashed when window was closed or context became invalid.

**Solution**:
- Added window closure checks before rendering
- Added error handling for context switching
- Added exception handling for display operations
- Added checks to skip rendering if window is invalid

**Key Changes**:
```python
# Check if window is closed
if not self._viz_window or not self._viz_window.is_focused():
    self._stop_flag.set()
    break

# Error handling for context switching
try:
    self._viz_window.backend.window.switch_to()
except Exception as e:
    print(f"Error switching to window context: {e}")
    self._stop_flag.set()
    break

# Error handling for display
try:
    self._viz_window.display(framebuffer)
except Exception as e:
    print(f"Error displaying frame: {e}")
    self._stop_flag.set()
    break
```

## Current State

The following protections are now in place:
- ✅ Fullscreen transitions are synchronized with render loop skipping
- ✅ Window close operations are thread-safe
- ✅ OpenGL cleanup has comprehensive error handling
- ✅ Texture operations have validation and error handling
- ✅ Render loop has error handling for invalid contexts

## Remaining Issues

Segfaults may still occur due to:
1. **Race conditions**: Thread synchronization may not be complete for all window operations
2. **macOS Metal/OpenGL context lifecycle**: System-level context management issues
3. **Pyglet window operations**: May not be fully synchronized with render thread
4. **OpenGL context invalidation**: Context may become invalid during system operations

## Recommendations for Future Work

1. **Thread Synchronization**: Add explicit locks around window operations
2. **Detailed Logging**: Add more logging around fullscreen transitions and window operations
3. **Event-Based Resize**: Use pyglet's event system for resize events instead of polling
4. **Context Validation**: Add OpenGL context validation before every OpenGL call
5. **Separate Contexts**: Consider using separate OpenGL contexts for rendering vs display
6. **Window Class Extension**: Refactor to extend Pyglet's Window class directly for better integration

## Related Files

- `src/cube/display/pyglet_backend.py` - Main window and OpenGL management
- `src/cube/render/visualization_runner.py` - Render loop and thread management
- `src/cube/display/visualization_window.py` - Window wrapper and close handling
- `src/cube/controller.py` - Main thread coordination and cleanup

## Testing Notes

When testing fullscreen transitions:
- Watch for Metal command buffer errors
- Monitor for segfaults during transitions
- Verify window closes cleanly with ESC key
- Check that rendering resumes after transition completes

