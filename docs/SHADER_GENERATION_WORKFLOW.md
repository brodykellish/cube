# Shader Generation Workflow

## Overview

The shader generation system uses Claude AI to create and edit GLSL shaders with automatic validation and cleanup.

## File Organization

- **`src/cube/ai/shader_agent.py`**: Core generation logic (822 lines)
- **`src/cube/ai/shader_prompts.py`**: System prompts for LLM (215 lines)
- **`src/cube/menu/prompt_menu.py`**: User interface integration

## Generation Workflow

### New Shader Generation

```
1. User enters prompt: "create a pulsing sphere"
2. LLM generates:
   FILENAME: pulsing_sphere.glsl
   // Shader code...
3. Write to: pulsing_sphere_tmp.glsl
4. Test compilation
5. If success:
   - Write to: pulsing_sphere.glsl
   - Delete: pulsing_sphere_tmp.glsl
6. If failure:
   - Retry up to 3 times
   - Delete all *_tmp.glsl files
   - No final file created
```

### Editing Existing Shader

```
1. User loads: rotating_cube.glsl
2. User requests: "make it spin faster"
3. LLM generates shader code (no filename)
4. Write to: rotating_cube_tmp.glsl
5. Test compilation
6. If success:
   - Overwrite: rotating_cube.glsl
   - Delete: rotating_cube_tmp.glsl
7. If failure:
   - Retry up to 3 times
   - Delete all rotating_cube_tmp.glsl files
   - Original rotating_cube.glsl unchanged
```

## LLM Prompts

### Generation Prompt
- **Requires**: `FILENAME: name.glsl` on first line
- **Format**: 1-3 words, lowercase, underscores only
- **Examples**: `spiral_tunnel.glsl`, `crystal_cave.glsl`
- **Full code**: Complete shader with all functions

### Editing Prompt
- **No filename line** (editing existing file)
- **Full code**: Complete modified shader
- **Preserves**: Original structure unless changes requested

### Error Fixing Prompt
- **No filename line** (fixing existing attempt)
- **Full code**: Complete fixed shader
- **Includes**: Comment explaining what was fixed

## File Naming Rules

### LLM Suggested Names
- 1-3 descriptive words
- Lowercase only
- Underscores between words
- Pattern: `^[a-z0-9_]+\.glsl$`

**Valid:**
- `spiral.glsl`
- `pulsing_sphere.glsl`
- `fractal_tunnel_3d.glsl`

**Invalid (fallback used):**
- `Spiral-Tunnel.glsl` (uppercase, dashes)
- `my shader.glsl` (spaces)
- `shader!.glsl` (special chars)

### Temp File Convention
- New generation: `{suggested_name}_tmp.glsl`
- Editing: `{existing_name}_tmp.glsl`
- All temp files deleted after success/failure

## Error Handling

### Compilation Errors
1. **Attempt 1**: Generate shader, write to temp, test
2. **Attempt 2**: Fix errors, write to new temp, test
3. **Attempt 3**: Final fix attempt, write to new temp, test
4. **All fail**: Delete all temps, return error

### API Errors
- No API key: Return error immediately
- Network issues: Return error, no files created
- Extraction failure: Return error, no files created

### Guarantees
- ✅ Original files never modified unless validation passes
- ✅ All temp files tracked and deleted
- ✅ No orphaned files on any failure path
- ✅ Atomic operations (all-or-nothing)

## Code Organization Benefits

### Before (Single File)
```
shader_agent.py: ~900 lines
  - Generation logic
  - 3 large system prompts (~300 lines)
  - Validation logic
  - Helper methods
```

### After (Split)
```
shader_agent.py: 822 lines
  - Generation logic
  - Validation logic
  - Helper methods
  - 3 one-line prompt builders

shader_prompts.py: 215 lines
  - GENERATION_PROMPT
  - EDITING_PROMPT
  - ERROR_FIXING_PROMPT
  - format_prompt_with_examples()
```

**Benefits:**
- Cleaner code organization
- Easy to update prompts without touching logic
- Prompts can be version controlled separately
- Reduced cognitive load when reading code

## Example Scenarios

### Scenario 1: Successful New Generation
```
User: "create a rotating torus"
LLM: FILENAME: rotating_torus.glsl
     // shader code...

Files created:
  1. rotating_torus_tmp.glsl (temp)
  2. rotating_torus.glsl (final)

Files remaining:
  - rotating_torus.glsl ✓
```

### Scenario 2: Failed New Generation
```
User: "create complex fractal"
Attempt 1: complex_fractal_tmp.glsl (fails)
Attempt 2: complex_fractal_tmp.glsl (fails, old deleted)
Attempt 3: complex_fractal_tmp.glsl (fails, old deleted)

Files remaining:
  - None (all temps deleted) ✓
```

### Scenario 3: Successful Edit
```
User: Editing sphere.glsl
Request: "add pulsing effect"

Files created:
  1. sphere_tmp.glsl (temp)

Files modified:
  2. sphere.glsl (updated)

Files remaining:
  - sphere.glsl (updated) ✓
```

### Scenario 4: Failed Edit
```
User: Editing tunnel.glsl
Request: "add impossible feature"
Attempt 1-3: All fail

Files modified:
  - None

Files remaining:
  - tunnel.glsl (original, unchanged) ✓
```

## Integration Points

### prompt_menu.py
```python
# New generation
result = agent.generate_shader_with_validation(
    user_prompt,
    "generation"
)

# Editing
result = agent.generate_shader_with_validation(
    edit_prompt,
    "editing",
    existing_shader_path=current_shader_path
)
```

### Result Handling
```python
if result.success:
    # result.shader_path points to final file
    # No temp files exist
    launch_visualization(result.shader_path)
else:
    # result.shader_path is None
    # All temp files cleaned up
    # Original file unchanged (for edits)
    show_error(result.error)
```

## Debugging

### Enable Debug Output
Uncomment line 84-85 in `ssh_keyboard.py`:
```python
if chars:
    print(f"DEBUG: Received {repr(chars)} (hex: {chars.encode('utf-8').hex()})")
```

### Check Temp Files
During development, temp files appear briefly:
```bash
# List all temp files
ls shaders/generated/*_tmp.glsl

# These should be automatically cleaned up
# If you see orphaned temps, file a bug
```

### Validation Logs
The agent prints detailed logs:
- API call status
- Filename extraction
- Temp file creation
- Compilation results
- Cleanup operations

## Future Enhancements

- [ ] Progress streaming via Queue (real-time updates)
- [ ] Parallel example finding (faster prompt building)
- [ ] Custom retry limits per user preference
- [ ] Checkpoint/resume for long generations
- [ ] Diff display for edits (show what changed)
