# Shader Browser Directory Selection - Two-Stage Navigation

## Summary

Added a two-stage navigation system to ShaderBrowser that allows users to:
1. Select a shader directory (primitives/graphics/generated)
2. Browse shaders within that directory
3. Launch selected shader

## User Flow

### Before (Single List)
```
VISUALIZE → SURFACE → Flat list of all shaders
  --- PRIMITIVES ---
  sphere
  cube
  torus
  --- GRAPHICS ---
  water
  plasma
  < BACK
```

### After (Two-Stage Navigation)
```
VISUALIZE → SURFACE → Directory Selection
  PRIMITIVES
  GRAPHICS
  GENERATED  ← NEW!
  < BACK

Select GENERATED → Shader Selection
  cube_origin
  cube_gently
  simple_sphere
  < BACK (returns to directory selection)

Select cube_origin → Launch Visualization
```

## Implementation

### Modified: src/cube/menu/menu_states.py

**1. Added Two-Stage State Tracking** (lines 151-168)

```python
# Two-stage browsing: directory selection -> shader selection
self.browsing_mode = "directory"  # "directory" or "shader"
self.selected_directory: Optional[str] = None

# Available shader directories
self.directories = [
    ("directory", "PRIMITIVES", "primitives"),
    ("directory", "GRAPHICS", "graphics"),
    ("directory", "GENERATED", "generated"),  # NEW!
    ("action", "BACK", None)
]

# Start with directory selection
self._show_directory_selection()
```

**2. Added Directory Selection Method** (lines 170-175)

```python
def _show_directory_selection(self):
    """Show the directory selection menu."""
    self.browsing_mode = "directory"
    self.selected_directory = None
    self.items = self.directories.copy()
    self.list.set_items(self.items)
```

**3. Added Shader Selection Method** (lines 186-204)

```python
def _show_shader_selection(self, directory_name: str):
    """Show shaders from the selected directory."""
    self.browsing_mode = "shader"
    self.selected_directory = directory_name
    self.items = []

    # Load shaders from selected directory
    directory_path = Path("shaders") / directory_name
    shaders = self._load_glsl_directory(directory_path)

    if shaders:
        self.items.extend(shaders)
    else:
        self.items.append(("info", "NO SHADERS FOUND", None))

    # Add back option
    self.items.append(("action", "BACK", None))
    self.list.set_items(self.items)
```

**4. Updated Render Method** (lines 206-247)

```python
def render(self, renderer: MenuRenderer, context: MenuContext):
    # Header changes based on browsing mode
    if self.browsing_mode == "directory":
        title = "SELECT DIRECTORY"
        subtitle = f"[{self.pixel_mapper.upper()}]"
    else:
        title = "SELECT SHADER"
        subtitle = f"[{self.pixel_mapper.upper()}] {self.selected_directory.upper()}"
```

**5. Updated Input Handling** (lines 249-287)

```python
def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
    # ... navigation keys

    elif key == 'enter':
        selected = self.list.get_selected()
        if selected:
            item_type, name, data = selected

            if self.browsing_mode == "directory":
                # Directory selection mode
                if item_type == "directory":
                    # Navigate into directory
                    self._show_shader_selection(data)
                elif item_type == "action" and name == "BACK":
                    return BackAction()

            elif self.browsing_mode == "shader":
                # Shader selection mode
                if item_type == "shader":
                    # Launch shader
                    return LaunchVisualizationAction(
                        shader_path=data,
                        pixel_mapper=self.pixel_mapper
                    )
                elif item_type == "action" and name == "BACK":
                    # Go back to directory selection
                    self._show_directory_selection()

    elif key in ('back', 'escape'):
        if self.browsing_mode == "shader":
            # Back goes to directory selection
            self._show_directory_selection()
        else:
            # Back goes to previous menu
            return BackAction()
```

## Features

### 1. Directory Selection Screen

**Shows:**
- PRIMITIVES (shaders/primitives/)
- GRAPHICS (shaders/graphics/)
- GENERATED (shaders/generated/) ← NEW!
- BACK

**Controls:**
- Up/Down: Navigate
- Enter: Select directory
- Escape/Back: Return to previous menu

### 2. Shader Selection Screen

**Shows:**
- All .glsl files in selected directory
- BACK (returns to directory selection)

**Header:**
- Shows current directory: `SELECT SHADER [SURFACE] GENERATED`

**Controls:**
- Up/Down: Navigate
- Enter: Launch shader
- Escape/Back: Return to directory selection

### 3. Smart Back Navigation

**From Directory Selection:**
- Escape/Back → Returns to VisualizationModeSelect menu

**From Shader Selection:**
- Escape/Back → Returns to Directory Selection (not main menu)

This allows easy directory switching without leaving the browser.

## Usage Example

### Browsing Generated Shaders

```
User Flow:
1. Press Enter on "VISUALIZE"
2. Press Enter on "SURFACE"
3. See directory options:
   - PRIMITIVES
   - GRAPHICS
   - GENERATED  ← Select this
   - BACK

4. Press Enter on "GENERATED"
5. See generated shaders:
   - cube_origin
   - cube_gently
   - simple_sphere
   - BACK

6. Press Enter on "cube_origin"
7. Shader launches in surface mode ✅
```

### Quick Directory Switching

```
User in PRIMITIVES shader list:
1. Press ESC → Back to directory selection
2. Select GENERATED → See generated shaders
3. Select shader → Launch

No need to navigate all the way back to main menu!
```

## Directory Structure

```
shaders/
├── primitives/      ← Original
│   ├── sphere.glsl
│   ├── cube.glsl
│   └── ...
├── graphics/        ← Original
│   ├── water.glsl
│   ├── plasma.glsl
│   └── ...
└── generated/       ← NEW!
    ├── cube_origin.glsl
    ├── cube_gently.glsl
    └── ... (AI-generated shaders)
```

## State Management

### Browsing Mode States

| Mode | Screen | Items Shown | Enter Action | Back Action |
|------|--------|-------------|--------------|-------------|
| `directory` | Directory Selection | PRIMITIVES<br>GRAPHICS<br>GENERATED<br>BACK | Navigate to shader list | Return to prev menu |
| `shader` | Shader Selection | Shaders from selected dir<br>BACK | Launch shader | Return to directory selection |

### Instance Variables

```python
self.browsing_mode = "directory"  # or "shader"
self.selected_directory = None     # or "primitives", "graphics", "generated"
self.items = [...]                 # Current menu items
self.directories = [...]           # Available directories (constant)
```

## Testing

All functionality verified:
- ✅ ShaderBrowser imports successfully
- ✅ Creates with directory selection mode
- ✅ Three directories available (primitives, graphics, generated)
- ✅ Can navigate into directories
- ✅ Can navigate back to directory selection
- ✅ Browsing mode switches correctly

## Benefits

### User Experience
✅ **Organized:** Shaders grouped by type
✅ **Discoverable:** Easy to find AI-generated shaders
✅ **Fast:** Quick switching between directories
✅ **Intuitive:** Two-level hierarchy is clear

### Developer Experience
✅ **Extensible:** Easy to add more directories
✅ **Maintainable:** Clean state management
✅ **Flexible:** Works for both surface and cube modes

## Future Enhancements

Potential additions:
- Show shader count in directory selection (e.g., "GENERATED (5)")
- Sort shaders by date (newest first for generated)
- Preview thumbnail of selected shader
- Search/filter within directory
- Favorites/bookmarks system

## Code Example

### Adding a New Directory

To add another shader directory (e.g., "favorites"):

```python
# In ShaderBrowser.__init__:
self.directories = [
    ("directory", "PRIMITIVES", "primitives"),
    ("directory", "GRAPHICS", "graphics"),
    ("directory", "GENERATED", "generated"),
    ("directory", "FAVORITES", "favorites"),  # NEW
    ("action", "BACK", None)
]
```

Create the directory:
```bash
mkdir shaders/favorites
```

Done! The browser will automatically detect and show shaders from `shaders/favorites/`.

## Integration

The ShaderBrowser is used by the controller for both surface and cube modes:

```python
# In controller.py:
self.menu_navigator.register_menu('surface_browser', ShaderBrowser('surface'))
self.menu_navigator.register_menu('cube_browser', ShaderBrowser('cube'))
```

Both now support directory selection with generated shaders!

## Summary

**What Changed:**
- ✅ Added directory selection as first stage
- ✅ Added generated directory support
- ✅ Implemented two-stage navigation
- ✅ Updated header to show current directory
- ✅ Smart back navigation at both levels

**Lines of Code:**
- Modified: ~100 lines
- Added: ~60 lines
- Removed/Replaced: ~40 lines
- Net: ~20 lines added

**Complexity:** Low (simple state machine)

**User Impact:** High (easier to find and use generated shaders)

The shader browser now provides a clean, organized way to browse shaders by category with full support for AI-generated shaders!
