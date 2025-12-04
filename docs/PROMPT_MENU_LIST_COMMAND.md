# Prompt Menu /list and /vis Commands

## Summary

Integrated ShaderBrowser into PromptMenuState to enable shader selection for editing, with /vis command to visualize the current shader without leaving prompt mode.

## New Workflow

### User Flow: Edit Existing Shader

```
1. Type /list
   ↓
   [Shader Browser Opens]

2. SELECT DIRECTORY
   - PRIMITIVES
   - GRAPHICS
   - GENERATED  ← Select
   - BACK
   ↓

3. SELECT SHADER [GENERATED]
   - cube_origin.glsl  ← Select
   - cube_gently.glsl
   - BACK
   ↓

4. [Editing Mode Activated]
   cube: [Editing cube_origin.glsl]
   cube: Describe modifications or press ESC to exit.
   ↓

5. User: "make it spin faster"
   → Shader modified
   ↓

6. Type /vis
   → Visualization launches
   ↓

7. Press ESC in visualization
   → Returns to prompt (still in editing mode)
   → Can continue editing or /vis again
```

## Implementation

### 1. Added Shader Browser to PromptMenuState

**File:** `src/cube/menu/prompt_menu.py` (lines 110-115)

```python
# Shader browser for /list command (no pixel mapper selection needed)
self.shader_browser = ShaderBrowser(
    pixel_mapper='surface',  # Default, not used for editing
    include_pixel_mapper=False
)
self.browser_active = False  # True when showing shader browser
```

### 2. Added /vis Command

**File:** `src/cube/menu/prompt_menu.py` (lines 127-130)

```python
self.commands = {
    'shader': {...},
    'list': {...},
    'vis': {  # NEW
        'agent': None,
        'description': 'Visualize current shader'
    }
}
```

### 3. Integrated Browser in Input Handling

**File:** `src/cube/menu/prompt_menu.py` (lines 198-212)

```python
# If browser is active, delegate to it
if self.browser_active:
    action = self.shader_browser.handle_input(key, context)

    if isinstance(action, ShaderSelectionAction):
        # User selected a shader - enter editing mode
        self.browser_active = False
        self.enter_editing_mode(action.shader_path)
        return None
    elif action:
        # Other actions (BackAction, etc.) - close browser
        self.browser_active = False
        return None

    return None
```

### 4. Integrated Browser in Rendering

**File:** `src/cube/menu/prompt_menu.py` (lines 500-503)

```python
# If browser is active, render it instead
if self.browser_active:
    self.shader_browser.render(renderer, context)
    return
```

### 5. Implemented /list Command Handler

**File:** `src/cube/menu/prompt_menu.py` (lines 326-331)

```python
if command_name == 'list':
    # Show shader browser for selecting shader to edit
    self.browser_active = True
    self.text_box.append_text(f"cube: [Browse shaders to edit]")
    self.status_message = "Browse shaders - Select one to edit"
    return None
```

### 6. Implemented /vis Command Handler

**File:** `src/cube/menu/prompt_menu.py` (lines 333-346)

```python
elif command_name == 'vis':
    # Visualize current shader
    if self.current_shader_path:
        self.text_box.append_text(f"cube: Visualizing {self.current_shader_name}...")
        return LaunchVisualizationAction(
            shader_path=self.current_shader_path,
            pixel_mapper='surface'  # Default to surface
        )
    else:
        self.text_box.append_text(f"> {command_input}")
        self.text_box.append_text(f"cube: ERROR - No shader loaded")
        self.text_box.append_text(f"cube: Use /shader to create or /list to load a shader first")
        self.status_message = "No shader loaded"
        return None
```

## Commands

### /shader
**Purpose:** Generate new shaders from natural language
**Behavior:** Enters generation mode, prompts for description
**Result:** Creates new shader, enters editing mode

### /list (NEW)
**Purpose:** Browse and select existing shader to edit
**Behavior:** Opens shader browser overlay
**Result:** Loads selected shader into editing mode

### /vis (NEW)
**Purpose:** Visualize current shader
**Behavior:** Launches visualization with current shader
**Result:** Shows shader, returns to prompt on ESC
**Requires:** A shader must be loaded (via /shader or /list)

## State Management

### Browser Overlay State

```python
self.browser_active = False  # Browser overlay shown?

# When True:
- Shader browser renders over prompt interface
- Input delegated to shader browser
- ShaderSelectionAction → enter editing mode
- BackAction → close browser

# When False:
- Normal prompt interface
- Text input active
- Commands processed
```

### Editing Mode State

```python
self.editing_mode = False  # Editing existing shader?
self.current_shader_path = None  # Path to shader being edited
self.current_shader_name = None  # Filename for display

# When True:
- Prompts modify existing shader
- /vis command available
- Header shows "EDIT: shader_name.glsl"

# When False:
- Prompts create new shaders
- /vis shows error (no shader loaded)
```

## Example Sessions

### Session 1: Create and Test New Shader

```
> /shader
cube: [Entered /shader mode]
> create a rotating sphere
cube: ...
cube: Created shader: sphere.glsl
cube: Launching visualization...
[ESC - returns to prompt]
> make it pulse with iParam0
cube: ...
[Shader updated]
> /vis
[Visualization launches]
```

### Session 2: Edit Existing Shader

```
> /list
cube: [Browse shaders to edit]
[Browser opens]
> [Select GENERATED → cube_origin.glsl]
cube: [Editing cube_origin.glsl]
> change the color to blue
cube: ...
[Shader updated]
> /vis
[Visualization launches with blue cube]
[ESC - returns to prompt]
> make it bigger
cube: ...
> /vis
[Visualization launches with bigger blue cube]
```

## Textbox Padding Fix

**Also Fixed:** Textbox now uses exactly 1 character width (4 pixels) of padding

**Before:**
- x = 5 or 10 pixels
- width = width - 10 or - 20
- Inconsistent padding

**After:**
- x = 4 pixels (1 character width)
- width = width - 8 pixels (4 on each side)
- Exactly 1 character padding on each edge

**Locations updated:**
1. Initial TextBox creation (line 82)
2. Render method textbox update (lines 539-540)
3. Input area positioning (lines 548, 551)

## Benefits

### User Experience
✅ **Control:** User decides when to visualize
✅ **Iterate:** Edit → /vis → ESC → Edit → /vis
✅ **Browse:** Easy access to existing shaders
✅ **Stay in Flow:** Never leaves prompt mode
✅ **Full Width:** Textbox uses all available space

### Developer Experience
✅ **Reusable:** ShaderBrowser used for both visualization and editing
✅ **Modular:** Browser is self-contained overlay
✅ **Clean:** Proper action-based communication

## Testing

Workflow verified:
- ✅ /list opens shader browser
- ✅ Browser shows directory selection
- ✅ Can navigate: PRIMITIVES, GRAPHICS, GENERATED
- ✅ Selecting shader enters editing mode
- ✅ ESC in browser returns to prompt
- ✅ /vis launches visualization
- ✅ ESC in visualization returns to prompt (editing mode preserved)
- ✅ Textbox uses full width with 1 char padding

## Summary

**Modified Files:**
- `src/cube/menu/prompt_menu.py` - Added browser integration, /vis command, textbox padding

**New Commands:**
- `/list` - Browse existing shaders
- `/vis` - Visualize current shader

**New Features:**
- Shader browser overlay in prompt mode
- Edit existing shaders without leaving prompt
- Iterative edit/test workflow
- Full-width textbox with proper padding

The prompt menu is now a complete shader editing environment!
