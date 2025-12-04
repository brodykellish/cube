# Shader System Bug Fixes

## Issues Fixed

### 1. Double Nesting: `shaders/generated/generated/`

**Problem**: Shaders were being saved in `/shaders/generated/generated/` instead of `/shaders/generated/`

**Root Cause**:
- Controller created `generated_dir = shaders_dir / 'generated'`
- Controller passed `generated_dir` to PromptMenuState
- PromptMenuState then did `shaders_dir / 'generated'` again
- Result: `shaders/generated/generated/`

**Fix** (src/cube/controller.py:130-132):
```python
# Before:
generated_dir = shaders_dir / 'generated'
self.menu_navigator.register_menu('prompt', PromptMenuState(..., generated_dir))

# After:
# Pass shaders_dir directly - PromptMenuState will create the 'generated' subdirectory
self.menu_navigator.register_menu('prompt', PromptMenuState(..., shaders_dir))
```

### 2. Useless Temp Filenames: `i_m.glsl`

**Problem**: When editing shaders, temp files had meaningless names like `i_m.glsl` instead of being related to the original shader

**Root Cause**:
The editing prompt contained text like:
```
I'm editing the shader 'set_triangular.glsl'.
Current code: ...
Modification request: can you make one parameter control the size of each prism?
```

The filename generator extracted words and removed stop words, leaving only `i`, `m` from "I'm", resulting in `i_m.glsl`.

**Fix** (src/cube/ai/shader_agent.py:773-780):
1. Added detection for editing prompts
2. Extracts original filename from the prompt
3. Uses `{original_name}_edit_temp.glsl` for temp files
4. Added more stop words including editing-related terms

```python
# Pattern: "I'm editing the shader 'filename.glsl'"
edit_match = re.search(r"editing.*?shader\s+['\"]([a-zA-Z0-9_]+)\.glsl['\"]", user_prompt, re.IGNORECASE)
if edit_match:
    original_name = edit_match.group(1)
    return f"{original_name}_edit_temp.glsl"
```

### 3. No Compilation Error Detection

**Problem**: The menu system wasn't using the validation workflow, so compilation errors weren't detected or retried

**Root Cause**:
- Menu called `generate_shader()` directly for both creation and editing
- The validation system (`generate_shader_with_validation()`) was never used
- Errors were only discovered when trying to launch the visualization

**Fix** (src/cube/menu/prompt_menu.py:369-373):
```python
# Before:
result = self.commands['shader']['agent'].generate_shader(
    user_prompt,
    error_feedback=self.last_error,
    prompt_type="generation"
)

# After:
# Creation mode - generate new shader WITH VALIDATION
# This will automatically detect and retry on compilation errors
result = self.commands['shader']['agent'].generate_shader_with_validation(
    user_prompt
)
```

**How It Works Now**:
1. New shader creation uses `generate_shader_with_validation()`
2. This automatically:
   - Tests compilation by running shader_preview.py for 3 seconds
   - Detects errors in output
   - Retries up to 3 times with error-fixing prompt
   - Provides complete error feedback to Claude
3. Editing mode still uses direct `generate_shader()` (faster, original shader already worked)

### 4. File Handling Bug (Also Fixed)

**Problem**: Empty shader files were created when editing

**Root Cause**:
```python
result.shader_path.unlink()  # Delete file
current.write_text(result.shader_path.read_text())  # Try to read deleted file
```

**Fix** (src/cube/menu/prompt_menu.py:358-363):
```python
# Read content BEFORE unlinking
generated_content = result.shader_path.read_text()
# Write to current shader
self.current_shader_path.write_text(generated_content)
# Remove temp generated file
result.shader_path.unlink()
```

## Summary of Changes

### Files Modified:

1. **src/cube/controller.py** (line 130-132)
   - Fixed double nesting by passing `shaders_dir` instead of `generated_dir`

2. **src/cube/menu/prompt_menu.py** (lines 347-373)
   - Added `prompt_type="editing"` for editing mode
   - Added `prompt_type="generation"` for creation mode
   - Switched creation mode to use `generate_shader_with_validation()`
   - Fixed file handling order (read before unlink)

3. **src/cube/ai/shader_agent.py** (lines 773-812)
   - Added filename preservation for editing mode
   - Detects editing prompts and extracts original filename
   - Uses descriptive temp filename: `{original}_edit_temp.glsl`
   - Added more stop words to improve filename generation

## Testing

### Before Fixes:
```
❌ Shaders saved in: /shaders/generated/generated/
❌ Temp files named: i_m.glsl
❌ No compilation error detection
❌ Empty shader files created
```

### After Fixes:
```
✅ Shaders saved in: /shaders/generated/
✅ Temp files named: set_triangular_edit_temp.glsl
✅ Automatic compilation error detection and retry
✅ Proper file content transfer
```

## User Experience Improvements

1. **Cleaner file structure**: No more double-nested directories
2. **Better temp filenames**: Can easily see which shader is being edited
3. **Automatic error recovery**: Failed shaders are retried up to 3 times with error feedback
4. **Reliable file saves**: No more empty shader files

## Workflow Now

### Creating a New Shader:
```
User: "create a rotating sphere"
  ↓
System: generate_shader_with_validation()
  ↓
Generate with "generation" prompt
  ↓
Test compilation (3 sec)
  ↓
✅ Success → Save & launch
❌ Error → Retry with "error_fixing" prompt + error details (up to 3 attempts)
```

### Editing an Existing Shader:
```
User: "make it spin faster"
  ↓
System: generate_shader(prompt_type="editing")
  ↓
Generate with "editing" prompt
  ↓
Save to temp file: {original}_edit_temp.glsl
  ↓
Read temp file content
  ↓
Write to original file
  ↓
Delete temp file
  ↓
Launch visualization
```

## Notes

- Editing mode doesn't use validation (faster, assumes original worked)
- If edited shader fails to compile, user sees error when launching
- Future: Could add optional validation for edits too
- All prompt types ("generation", "editing", "error_fixing") now properly used
