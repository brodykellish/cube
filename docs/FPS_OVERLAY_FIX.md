# FPS Overlay Fix

## Problem

After implementing the 3-layer architecture, the FPS debug overlay stopped appearing in menu mode, even though it previously worked.

## Root Cause

The menu mode rendering logic was clearing the debug layer when debug UI was disabled, but it wasn't rendering anything to the debug layer when debug UI **was** enabled. The `_render_menu_debug_overlay()` method was being called but didn't exist.

## Solution

### 1. Added Menu FPS Tracking

Added FPS tracking variables specifically for menu mode in `controller.py` `__init__`:

```python
# Menu FPS tracking
self.menu_frame_count = 0
self.menu_fps = 0.0
self.menu_fps_frames = 0
self.menu_last_fps_time = time.time()
```

### 2. Added FPS Calculation in Menu Mode

Added FPS calculation logic in the menu mode section of the main loop:

```python
# Update menu FPS
self.menu_frame_count += 1
self.menu_fps_frames += 1
current_time = time.time()
if current_time - self.menu_last_fps_time >= 1.0:
    self.menu_fps = self.menu_fps_frames / (current_time - self.menu_last_fps_time)
    self.menu_last_fps_time = current_time
    self.menu_fps_frames = 0
```

### 3. Implemented `_render_menu_debug_overlay()` Method

Created the menu debug overlay rendering method (similar to shader mode):

```python
def _render_menu_debug_overlay(self):
    """Render debug UI overlay for menu mode."""
    # Clear debug layer
    self.debug_layer[:, :] = 0

    # Render menu FPS counter in top-left corner on debug layer
    fps_text = f"FPS {self.menu_fps:.1f}"
    debug_renderer = MenuRenderer(self.debug_layer)
    debug_renderer.draw_text(fps_text, x=2, y=2, color=(0, 255, 0), scale=1)
```

## How It Works

### Layer Stack

```
┌─────────────────────────────┐
│  Layer 2: Debug Overlay     │  ← FPS counter rendered here
│  - Green text "FPS XX.X"    │
│  - Top-left corner (2, 2)   │
├─────────────────────────────┤
│  Layer 1: Shader            │  ← Shader output (when in shader mode)
│  - OpenGL rendered pixels   │
├─────────────────────────────┤
│  Layer 0: Menu              │  ← Menu UI (when in menu mode)
│  - Navigation, text, etc.   │
└─────────────────────────────┘
```

### Menu Mode Rendering Flow

```python
# Main loop - Menu Mode
1. Handle input events
2. Clear shader layer (not used)
3. Render menu to Layer 0
4. If debug_ui enabled:
   - Calculate menu FPS
   - Render FPS to Layer 2
   Else:
   - Clear Layer 2
5. Composite all layers
6. Display result
```

### Shader Mode Rendering Flow

```python
# Main loop - Shader Mode
1. Handle input events (camera, reload, ESC)
2. Clear menu layer (not used)
3. Render shader with OpenGL
4. Read pixels to Layer 1
5. If debug_ui enabled:
   - Get shader stats
   - Render FPS to Layer 2
   Else:
   - Clear Layer 2
6. Composite all layers
7. Display result with OpenGL
```

## Testing

### Enable Debug UI

1. Start cube-control: `python cube_control.py --width 64 --height 64`
2. Navigate to **SETTINGS**
3. Select **DEBUG UI** and press Enter to toggle **ON**
4. Press ESC to return to main menu
5. **Expected**: Green "FPS XX.X" text appears in top-left corner of menu

### Test in Shader Mode

1. From main menu, navigate to **VISUALIZE**
2. Select any shader
3. **Expected**: Green "FPS XX.X" text appears in top-left corner on top of shader

### Test Mode Switching

1. With debug UI enabled, view a shader
2. Press ESC to return to menu
3. **Expected**: FPS counter persists and updates correctly in both modes

## Files Modified

### `src/piomatter/menu/controller.py`

**Lines 67-71**: Added menu FPS tracking variables
```python
# Menu FPS tracking
self.menu_frame_count = 0
self.menu_fps = 0.0
self.menu_fps_frames = 0
self.menu_last_fps_time = time.time()
```

**Lines 178-185**: Added menu FPS calculation
```python
# Update menu FPS
self.menu_frame_count += 1
self.menu_fps_frames += 1
current_time = time.time()
if current_time - self.menu_last_fps_time >= 1.0:
    self.menu_fps = self.menu_fps_frames / (current_time - self.menu_last_fps_time)
    self.menu_last_fps_time = current_time
    self.menu_fps_frames = 0
```

**Lines 329-337**: Added `_render_menu_debug_overlay()` method
```python
def _render_menu_debug_overlay(self):
    """Render debug UI overlay for menu mode."""
    self.debug_layer[:, :] = 0
    fps_text = f"FPS {self.menu_fps:.1f}"
    debug_renderer = MenuRenderer(self.debug_layer)
    debug_renderer.draw_text(fps_text, x=2, y=2, color=(0, 255, 0), scale=1)
```

## Related Documentation

- `THREE_LAYER_ARCHITECTURE.md` - Layer system overview
- `FIXES_SUMMARY.md` - Previous fixes and improvements
- `UNIFIED_DISPLAY_ARCHITECTURE.md` - Overall architecture
