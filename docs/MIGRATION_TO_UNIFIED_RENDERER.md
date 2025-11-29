# Migration to Standalone UnifiedRenderer

**Date:** 2025-11-28

This document describes the migration from the menu-integrated shader renderer to the standalone `UnifiedRenderer` with input abstraction.

## Summary

The cube control system has been migrated to use the new standalone shader module (`shader/unified_renderer.py`) instead of the menu-specific implementation. This provides better separation of concerns, cleaner architecture, and extensible input handling.

## Changes Made

### 1. Backed Up Old Files

Created `menu/backup/` directory containing:
- `unified_shader_renderer.py.old` - Original menu-integrated renderer
- `camera_modes.py.old` - Original camera mode implementations
- `README.md` - Documentation of backups

### 2. Updated Imports in `menu/controller.py`

**Before:**
```python
from .unified_shader_renderer import UnifiedShaderRenderer
from .camera_modes import SphericalCamera, StaticCamera
```

**After:**
```python
from ..shader import UnifiedRenderer, SphericalCamera, StaticCamera
```

### 3. Updated Type Hints

**Before:**
```python
self.shader_renderer: Optional[UnifiedShaderRenderer] = None
```

**After:**
```python
self.shader_renderer: Optional[UnifiedRenderer] = None
```

### 4. Updated Instantiation

**Before:**
```python
self.shader_renderer = UnifiedShaderRenderer(self.width, self.height)
```

**After:**
```python
self.shader_renderer = UnifiedRenderer(self.width, self.height, windowed=False)
```

The `windowed=False` parameter ensures offscreen rendering (GLUT/EGL) for the menu system.

### 5. Added Cleanup Call

**Before:**
```python
def _exit_shader_mode(self):
    self.shader_renderer = None
    # ...
```

**After:**
```python
def _exit_shader_mode(self):
    if self.shader_renderer is not None:
        try:
            self.shader_renderer.cleanup()
        except Exception as e:
            print(f"Warning: Error cleaning up shader renderer: {e}")
    self.shader_renderer = None
    # ...
```

Properly cleans up OpenGL context and input sources.

## API Compatibility

The new `UnifiedRenderer` maintains API compatibility with the old `UnifiedShaderRenderer`:

| Method | Old API | New API | Notes |
|--------|---------|---------|-------|
| Constructor | `UnifiedShaderRenderer(width, height)` | `UnifiedRenderer(width, height, windowed=False)` | Added windowed parameter |
| Load shader | `load_shader(path)` | `load_shader(path)` | ✓ Compatible |
| Set camera | `set_camera_mode(mode)` | `set_camera_mode(mode)` | ✓ Compatible |
| Reset camera | `reset_camera()` | `reset_camera()` | ✓ Compatible |
| Render | `render()` | `render()` | ✓ Compatible |
| Read pixels | `read_pixels()` | `read_pixels()` | ✓ Compatible |
| Handle input | `handle_input(key, pressed)` | `handle_input(key, pressed)` | ✓ Compatible |
| Get stats | `get_stats()` | `get_stats()` | ✓ Compatible |
| Cleanup | N/A | `cleanup()` | New method (was in `__del__`) |

### Camera Modes

Camera mode classes are identical and work the same way:
- `SphericalCamera` - Orbit camera with spherical coordinates
- `StaticCamera` - Fixed camera position

## Benefits

### 1. Separation of Concerns
- Rendering logic separated from menu logic
- Menu system is now just a consumer of the shader module
- Easier to understand and maintain

### 2. Input Abstraction
The new system uses `InputManager` for extensible input handling:

```python
renderer = UnifiedRenderer(64, 64)
renderer.add_input_source(AudioFileInput("music.mp3"))
renderer.add_input_source(MicrophoneInput())
```

Keyboard input is added by default, and additional sources can be added dynamically.

### 3. Reusability
The shader renderer can now be used in any context:

```python
# Standalone windowed application
from adafruit_blinka_raspberry_pi5_piomatter.shader import UnifiedRenderer

renderer = UnifiedRenderer(64, 64, windowed=True)
renderer.load_shader("my_shader.glsl")

while running:
    renderer.render()
    running = renderer.handle_events()
```

### 4. Better Testing
Standalone components can be unit tested independently without the menu system.

### 5. Future Extensibility
Easy to add new features:
- New input sources (gamepad, OSC, serial, etc.)
- New camera modes (FPS, flying, etc.)
- Audio reactivity improvements
- Video feed inputs

## Verification

All imports and basic functionality verified:

```bash
# Controller imports successfully
python3 -c "from src.adafruit_blinka_raspberry_pi5_piomatter.menu.controller import CubeController; print('✓')"

# Shader module exports work
python3 -c "from src.adafruit_blinka_raspberry_pi5_piomatter.shader import UnifiedRenderer, SphericalCamera; print('✓')"
```

## Usage Examples

### Menu System (Current Usage)

The menu system automatically uses the new renderer:

```bash
python cube_control.py --width 64 --height 64
```

No changes needed for end users!

### Standalone Application

You can now create standalone shader applications:

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import (
    UnifiedRenderer, AudioFileInput, SphericalCamera
)

# Create windowed preview
renderer = UnifiedRenderer(64, 64, windowed=True, scale=8)
renderer.set_camera_mode(SphericalCamera())
renderer.add_input_source(AudioFileInput("track.mp3", bpm=140))
renderer.load_shader("shaders/visualizer.glsl")

# Interactive loop
running = True
while running:
    renderer.render()
    running = renderer.handle_events()

renderer.cleanup()
```

### LED Matrix Application

For LED matrix output:

```python
from adafruit_blinka_raspberry_pi5_piomatter.shader import UnifiedRenderer

# Offscreen rendering
renderer = UnifiedRenderer(64, 64, windowed=False)
renderer.load_shader("shaders/cube.glsl")

# Render loop
while True:
    renderer.render()
    pixels = renderer.read_pixels()  # numpy array (64, 64, 3)

    # Display on LED matrix
    matrix.show(pixels)

renderer.cleanup()
```

## Rollback Instructions

If you need to restore the old menu-integrated renderer:

```bash
# Restore backed up files
cp src/adafruit_blinka_raspberry_pi5_piomatter/menu/backup/unified_shader_renderer.py.old \
   src/adafruit_blinka_raspberry_pi5_piomatter/menu/unified_shader_renderer.py

cp src/adafruit_blinka_raspberry_pi5_piomatter/menu/backup/camera_modes.py.old \
   src/adafruit_blinka_raspberry_pi5_piomatter/menu/camera_modes.py
```

Then revert `menu/controller.py` imports:

```python
# Change this:
from ..shader import UnifiedRenderer, SphericalCamera, StaticCamera

# Back to this:
from .unified_shader_renderer import UnifiedShaderRenderer
from .camera_modes import SphericalCamera, StaticCamera

# And change:
self.shader_renderer = UnifiedRenderer(self.width, self.height, windowed=False)

# Back to:
self.shader_renderer = UnifiedShaderRenderer(self.width, self.height)
```

## Documentation

New documentation added:
- `docs/INPUT_ABSTRACTION.md` - Complete input system documentation
- `menu/backup/README.md` - Backup file documentation

Existing documentation updated:
- `shader/__init__.py` - Added new exports and docstrings

## Future Work

Potential enhancements enabled by this architecture:

1. **Enhanced Audio Input**
   - Real-time FFT analysis
   - Beat detection improvements
   - MIDI support

2. **Additional Input Sources**
   - Game controller support
   - OSC (Open Sound Control) for music software
   - Serial input from Arduino/sensors
   - Network sockets for remote control

3. **Camera Modes**
   - FPS camera (first-person navigation)
   - Flying camera (bird's-eye view)
   - Path-based camera animation

4. **Video Input**
   - Webcam feed as texture
   - Video file playback
   - Screen capture

5. **Input Recording/Playback**
   - Record input sequences
   - Deterministic replay
   - Automated testing

## Conclusion

The migration to `UnifiedRenderer` provides a cleaner, more maintainable architecture while maintaining full backward compatibility. The menu system works exactly as before, but now uses a standalone, well-documented shader module that can be used in any context.

## See Also

- `docs/INPUT_ABSTRACTION.md` - Input abstraction documentation
- `docs/CAMERA_MODES.md` - Camera mode documentation
- `docs/SHADER_INPUT.md` - Shader input system overview
- `shader/unified_renderer.py` - New renderer implementation
- `shader/input_sources.py` - Input source implementations
- `menu/backup/README.md` - Backup file documentation
