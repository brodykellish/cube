# Shader Agent Validation

The ShaderAgent now includes automatic compilation error detection and retry logic with specialized system prompts for different tasks.

## Overview

When generating shaders, the agent can now:
1. Generate a shader from a natural language prompt
2. Test the shader by attempting to render it
3. Detect compilation errors in the output
4. Automatically retry with specialized error-fixing prompts up to 3 times

## Specialized System Prompts

The agent uses three distinct system prompts optimized for different tasks:

### 1. Generation Prompt (`prompt_type="generation"`)
Used for **initial shader creation** from user descriptions.
- Emphasizes creativity and visual interest
- Guides on shader patterns and MIDI parameter usage
- Stresses outputting the **complete .glsl file** (no placeholders)
- Includes relevant example shaders for reference

### 2. Editing Prompt (`prompt_type="editing"`)
Used for **refining existing shaders** based on user feedback.
- Focuses on modifying existing code while preserving structure
- Warns against using placeholders like "// rest unchanged"
- Emphasizes outputting the **complete modified .glsl file**
- Maintains consistency with original shader style

### 3. Error Fixing Prompt (`prompt_type="error_fixing"`)
Used for **fixing compilation errors** in failed shaders.
- Specialized for debugging GLSL compilation errors
- Lists common error types (undeclared identifiers, type mismatches, etc.)
- Provides debugging approach and error resolution strategies
- Emphasizes outputting the **complete fixed .glsl file**
- References working shader examples for correct syntax

## Usage

### Basic Generation with Validation

```python
from pathlib import Path
from cube.ai import ShaderAgent

# Initialize agent
shaders_dir = Path('shaders/generated')
agent = ShaderAgent(shaders_dir)

# Generate shader with automatic validation and retry
result = agent.generate_shader_with_validation(
    "Create a pulsing sphere with rainbow colors"
)

if result.success:
    print(f"✅ Shader generated: {result.shader_path}")
else:
    print(f"❌ Failed: {result.error}")
```

### How It Works

1. **Initial Generation**: The agent generates a shader using the "generation" prompt
2. **Compilation Test**: Runs `shader_preview.py` for 3 seconds to test rendering
3. **Error Detection**: Checks output for compilation errors
4. **Retry with Error Fixing**: If errors found, switches to "error_fixing" prompt with:
   - The complete previous shader code
   - Full compilation error output
   - Specialized debugging instructions
5. **Maximum Attempts**: Tries up to 3 times before giving up

**Key Feature**: Each retry uses the specialized error-fixing prompt that includes the previous shader code and error messages, allowing Claude to see exactly what went wrong and fix it.

### Error Detection

The agent detects these error patterns:
- `ERROR:` or `error:`
- `compilation failed`
- `shader compilation error`
- `GLSL compilation failed`
- `syntax error`
- `undeclared identifier`
- `no matching overloaded function`
- Python tracebacks
- OpenGL errors

### Comparison: With vs Without Validation

**Without validation** (original method):
```python
result = agent.generate_shader(
    "Create a rotating cube"
)
# Returns immediately, no compilation testing
```

**With validation** (new method):
```python
result = agent.generate_shader_with_validation(
    "Create a rotating cube"
)
# Tests compilation, retries if errors detected
# Maximum 3 attempts before giving up
```

## Configuration

The validation behavior is controlled by:
- `max_attempts = 3` (hardcoded in `generate_shader_with_validation`)
- Test timeout: 3 seconds per shader test
- Error feedback: Automatically extracted from compilation output

## Complete File Output Guarantee

**Critical**: All system prompts emphasize outputting the **complete .glsl file** with no omissions:

- ❌ No placeholders like `// ... rest of code` or `// same as before`
- ❌ No shortcuts like `// keep existing functions`
- ❌ No partial outputs requiring manual completion
- ✅ Every response contains the full, compilable shader code
- ✅ The output can be saved directly to a .glsl file and run immediately

This is especially important for:
- **Error fixing**: Claude must see and output the entire shader, not just the fix
- **Editing**: Even small changes require outputting the complete modified file
- **Validation retries**: Each attempt includes the full previous shader code

## Direct API Usage

You can also use specific prompt types directly:

```python
# Initial generation (default)
result = agent.generate_shader(
    "Create a rotating sphere",
    prompt_type="generation"
)

# Edit an existing shader
result = agent.generate_shader(
    "Make the colors more vibrant in this shader:\n\n```glsl\n...\n```",
    prompt_type="editing"
)

# Fix compilation errors
result = agent.generate_shader(
    "Fix errors in this shader:\n\n```glsl\n...\n```",
    error_feedback="ERROR: undeclared identifier: foo",
    prompt_type="error_fixing"
)
```

## Notes

- If `shader_preview.py` is not available, validation is skipped
- The agent maintains conversation history across retries
- Error feedback includes relevant error lines (truncated to 2000 chars)
- Successfully compiled shaders return immediately (no wasted attempts)
- Each prompt type is optimized for its specific task
- The error-fixing prompt includes common GLSL error patterns and debugging strategies
