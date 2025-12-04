# Shader Browser Refactoring - Flexible Selection System

## Summary

Refactored `ShaderBrowser` to return shader selection results instead of directly launching visualizations, with optional pixel mapper selection for different use cases.

## Changes

### 1. New Action Type: ShaderSelectionAction

**File:** `src/cube/menu/actions.py` (lines 56-60)

```python
@dataclass
class ShaderSelectionAction(MenuAction):
    """Shader selected from browser (may or may not include pixel mapper)."""
    shader_path: Path
    pixel_mapper: Optional[Literal['surface', 'cube']] = None
```

**Returns:**
- `shader_path`: Path to selected shader file
- `pixel_mapper`: Selected rendering mode ('surface' or 'cube'), or None

### 2. Flexible ShaderBrowser Constructor

**File:** `src/cube/menu/menu_states.py` (lines 140-147)

```python
def __init__(self, pixel_mapper: Optional[str] = None, include_pixel_mapper: bool = True):
    """
    Initialize shader browser.

    Args:
        pixel_mapper: Fixed pixel mapper ('surface' or 'cube'), or None to let user choose
        include_pixel_mapper: If True, include pixel mapper selection as first stage
    """
```

**Parameters:**
- `pixel_mapper`: If provided, skips pixel mapper selection and uses this mode
- `include_pixel_mapper`: If True, shows pixel mapper selection (only if pixel_mapper is None)

### 3. Three-Stage Navigation

**Stages:**
1. **Pixel Mapper Selection** (optional) - Choose SURFACE or CUBE
2. **Directory Selection** - Choose PRIMITIVES, GRAPHICS, or GENERATED
3. **Shader Selection** - Choose individual .glsl file

### 4. Controller Integration

**File:** `src/cube/controller.py` (lines 241-252)

```python
elif isinstance(action, ShaderSelectionAction):
    # Convert shader selection to visualization launch
    if action.pixel_mapper:
        launch_action = LaunchVisualizationAction(
            shader_path=action.shader_path,
            pixel_mapper=action.pixel_mapper
        )
        self._launch_visualization(launch_action)
    else:
        print(f"Warning: Shader selected but no pixel mapper specified")
    return True
```

## Usage Examples

### Example 1: Current Visualize Menu (Fixed Mode)

```python
# Registration
self.menu_navigator.register_menu('surface_browser', ShaderBrowser(pixel_mapper='surface'))
self.menu_navigator.register_menu('cube_browser', ShaderBrowser(pixel_mapper='cube'))
```

**User Flow:**
```
VISUALIZE → SURFACE
  ↓
SELECT DIRECTORY [SURFACE]
  PRIMITIVES
  GRAPHICS
  GENERATED
  BACK
  ↓
SELECT SHADER [SURFACE] GENERATED
  cube_origin.glsl  ← Select
  ↓
Returns: ShaderSelectionAction(shader_path=..., pixel_mapper='surface')
  ↓
Controller converts to LaunchVisualizationAction
  ↓
Visualization launches ✅
```

**Stages:** 2 (directory → shader)

### Example 2: Main Menu (Choose Mode)

```python
# Registration (if you want this)
self.menu_navigator.register_menu('browser', ShaderBrowser())
```

**User Flow:**
```
MAIN → BROWSE SHADERS
  ↓
SELECT MODE
  SURFACE  ← Select
  CUBE
  BACK
  ↓
SELECT DIRECTORY [SURFACE]
  PRIMITIVES
  GRAPHICS
  GENERATED
  BACK
  ↓
SELECT SHADER [SURFACE] GENERATED
  cube_origin.glsl  ← Select
  ↓
Returns: ShaderSelectionAction(shader_path=..., pixel_mapper='surface')
```

**Stages:** 3 (pixel_mapper → directory → shader)

### Example 3: Prompt /list Command (For Editing)

```python
# In prompt menu /list handler
browser = ShaderBrowser(pixel_mapper='surface', include_pixel_mapper=False)
# Or just: ShaderBrowser(pixel_mapper='surface')
# pixel_mapper can be any value or None - ignored for editing

# Navigate to browser
# When user selects shader, receive ShaderSelectionAction
# Use action.shader_path to enter editing mode
```

**User Flow:**
```
/list
  ↓
SELECT DIRECTORY [SURFACE]
  PRIMITIVES
  GRAPHICS
  GENERATED
  BACK
  ↓
SELECT SHADER [SURFACE] GENERATED
  cube_origin.glsl  ← Select
  ↓
Returns: ShaderSelectionAction(shader_path=..., pixel_mapper='surface')
  ↓
Prompt menu enters editing mode with shader_path ✅
```

**Stages:** 2 (directory → shader)

## Configuration Matrix

| Constructor | Pixel Mapper Selection | Directory Selection | Shader Selection | Use Case |
|-------------|----------------------|--------------------|--------------------|----------|
| `ShaderBrowser()` | ✅ | ✅ | ✅ | Main menu - choose everything |
| `ShaderBrowser('surface')` | ❌ | ✅ | ✅ | Visualize→Surface - mode known |
| `ShaderBrowser('cube')` | ❌ | ✅ | ✅ | Visualize→Cube - mode known |
| `ShaderBrowser(pixel_mapper='surface', include_pixel_mapper=False)` | ❌ | ✅ | ✅ | Prompt /list - mode irrelevant |

## Return Values

### ShaderSelectionAction Fields

```python
@dataclass
class ShaderSelectionAction:
    shader_path: Path          # Path to selected .glsl file
    pixel_mapper: Optional[str]  # 'surface', 'cube', or None
```

**When pixel_mapper is:**
- `'surface'` or `'cube'`: Can launch visualization directly
- `None`: Useful for editing mode where rendering mode doesn't matter

## Integration Points

### 1. Main Menu / VisualizationModeSelect

Uses existing separate browsers:
- `surface_browser` → ShaderBrowser('surface')
- `cube_browser` → ShaderBrowser('cube')

**Behavior:** Returns `ShaderSelectionAction`, controller launches visualization

### 2. Controller

Handles `ShaderSelectionAction`:
```python
if isinstance(action, ShaderSelectionAction):
    if action.pixel_mapper:
        # Launch visualization
        launch_action = LaunchVisualizationAction(
            shader_path=action.shader_path,
            pixel_mapper=action.pixel_mapper
        )
        self._launch_visualization(launch_action)
```

### 3. Prompt Menu /list Command (Future)

Will create browser and handle result:
```python
def _handle_list_command(self):
    # Create browser without pixel mapper requirement
    browser = ShaderBrowser(pixel_mapper='surface', include_pixel_mapper=False)

    # Navigate to browser
    # ...

    # When ShaderSelectionAction returned:
    # Enter editing mode with action.shader_path
```

## Backwards Compatibility

**Existing registrations work without changes:**
```python
# These still work as before
ShaderBrowser('surface')  # Fixed surface mode
ShaderBrowser('cube')     # Fixed cube mode
```

**Behavior changes:**
- ❌ No longer returns `LaunchVisualizationAction` directly
- ✅ Now returns `ShaderSelectionAction`
- ✅ Controller handles conversion to launch action
- ✅ Same end result for visualization
- ✅ Enables new use cases (editing mode)

## Benefits

### Separation of Concerns
- ✅ Browser selects shader (doesn't decide what to do with it)
- ✅ Controller decides action (launch visualization, edit, etc.)
- ✅ Reusable for different workflows

### Flexibility
- ✅ Can include or exclude pixel mapper selection
- ✅ Works for visualization mode
- ✅ Works for editing mode
- ✅ Works for any future use case

### User Experience
- ✅ Same familiar navigation
- ✅ Supports generated shaders
- ✅ Clean separation between mode selection and shader selection

## Testing

All configurations verified:
- ✅ ShaderBrowser('surface') → directory mode
- ✅ ShaderBrowser('cube') → directory mode
- ✅ ShaderBrowser() → pixel_mapper mode
- ✅ ShaderBrowser(include_pixel_mapper=False, pixel_mapper='surface') → directory mode
- ✅ Returns ShaderSelectionAction correctly
- ✅ Controller handles ShaderSelectionAction
- ✅ Launches visualization when pixel_mapper provided

## Next Steps (For User)

To implement /list command in prompt menu:

```python
# In prompt_menu.py, add to _handle_command method:

elif command_name == 'list':
    # Show shader browser for editing
    # Store that we're in list mode
    self.list_mode = True

    # Navigate to a shader browser (mode doesn't matter for editing)
    # You'll need to either:
    # A) Create and show the browser inline, or
    # B) Navigate to a browser and handle the ShaderSelectionAction

# When ShaderSelectionAction is received:
if self.list_mode and isinstance(action, ShaderSelectionAction):
    # Enter editing mode
    self.current_shader_path = action.shader_path
    self.current_shader_name = action.shader_path.name
    self.editing_mode = True
    self.text_box.append_text(f"cube: Loaded {action.shader_path.name} for editing")
    self.text_box.append_text(f"cube: Describe your changes...")
    self.list_mode = False
```

## Summary

**Modified Files:**
- `src/cube/menu/actions.py` - Added ShaderSelectionAction
- `src/cube/menu/menu_states.py` - Refactored ShaderBrowser
- `src/cube/controller.py` - Handle ShaderSelectionAction

**Lines Changed:** ~100 lines

**Complexity:** Medium

**Benefits:**
- ✅ More flexible shader browser
- ✅ Supports multiple workflows
- ✅ Cleaner separation of concerns
- ✅ Enables future features (editing mode)

The shader browser is now a reusable component that returns selections without dictating what to do with them!
