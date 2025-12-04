# Shader Agent Updates - Complete File Output & Error Fixing

## Summary of Changes

The shader agent has been significantly enhanced with:
1. **Three specialized system prompts** for different tasks
2. **Complete file output guarantee** (no placeholders or omissions)
3. **Automatic compilation error detection and retry** with specialized debugging prompts

## Key Improvements

### 1. Specialized System Prompts

Three distinct prompts optimized for specific tasks:

| Prompt Type | Used For | Key Features |
|-------------|----------|--------------|
| **Generation** | Initial shader creation | Emphasizes creativity, patterns, complete file output |
| **Editing** | Modifying existing shaders | Preserves structure, warns against placeholders |
| **Error Fixing** | Fixing compilation errors | Debugging strategies, common error patterns, complete fixed file |

### 2. Complete File Output Guarantee

**All prompts strictly enforce:**
- ✅ Output the **COMPLETE** .glsl file from start to finish
- ✅ Include ALL functions, SDFs, lighting, mainImage, etc.
- ❌ NO placeholders like `// ... rest of code` or `// same as before`
- ❌ NO shortcuts like `// keep existing functions`
- ✅ Ready to save and compile immediately

### 3. Smart Error Retry Loop

When compilation fails, the agent:
1. Captures the full error output
2. Reads the previous shader code
3. Switches to the **error_fixing** prompt
4. Provides Claude with:
   - Complete previous shader code
   - Full compilation error messages
   - Debugging strategies and common error patterns
5. Retries up to 3 times before giving up

## Implementation Details

### Modified Files

**src/cube/ai/shader_agent.py**:
- Added `prompt_type` parameter to `generate_shader()` (line 76)
- Created `_build_generation_prompt()` (line 504)
- Created `_build_editing_prompt()` (line 586)
- Created `_build_error_fixing_prompt()` (line 650)
- Updated `generate_shader_with_validation()` to use error_fixing prompt on retry (line 230)
- Updated `refine_shader()` to use editing prompt (line 426)
- Enhanced error retry loop to include previous shader code (line 273)

### New Files

**docs/shader_agent_validation.md**:
- Comprehensive documentation of validation system
- Explains all three prompt types
- Usage examples and configuration

**docs/prompt_types_example.md**:
- Detailed workflow examples
- Shows how prompts differ
- Complete scenario walkthroughs

**test_prompt_types.py**:
- Demonstrates all three prompt types
- Shows key features of each prompt
- Validates implementation

**test_validation.py**:
- Tests shader generation with validation
- Verifies error detection and retry

## Usage Examples

### Basic Generation with Validation
```python
from cube.ai import ShaderAgent
from pathlib import Path

agent = ShaderAgent(Path('shaders/generated'))

# Automatic validation and error retry
result = agent.generate_shader_with_validation(
    "Create a pulsing sphere with rainbow colors"
)
```

### Manual Prompt Type Selection
```python
# Initial generation
result = agent.generate_shader(
    "Create a rotating cube",
    prompt_type="generation"
)

# Edit existing shader
result = agent.generate_shader(
    f"Make it spin faster:\n\n```glsl\n{shader_code}\n```",
    prompt_type="editing"
)

# Fix compilation errors
result = agent.generate_shader(
    f"Fix errors in:\n\n```glsl\n{failed_shader}\n```",
    error_feedback="ERROR: undeclared identifier: foo",
    prompt_type="error_fixing"
)
```

### Using Convenience Methods
```python
# Automatic editing prompt
result = agent.refine_shader("Add more color variation")

# Automatic validation workflow (generation → error_fixing)
result = agent.generate_shader_with_validation("Create a torus")
```

## Workflow Diagram

```
User Request: "Create a rotating sphere"
        ↓
[GENERATION PROMPT] → Generate shader v1
        ↓
Test compilation
        ↓
    ✅ Success? → Return shader
        ↓
    ❌ Failed
        ↓
[ERROR_FIXING PROMPT] + error feedback + previous code → Generate shader v2
        ↓
Test compilation
        ↓
    ✅ Success? → Return shader
        ↓
    ❌ Failed
        ↓
[ERROR_FIXING PROMPT] + error feedback + previous code → Generate shader v3
        ↓
Test compilation
        ↓
    ✅ Success? → Return shader
    ❌ Failed → Give up after 3 attempts
```

## Benefits

### For Shader Generation:
- Higher first-time compilation success rate
- Complete, ready-to-use shader files
- No manual fixes needed for common errors
- Better debugging with specialized prompts

### For Shader Editing:
- Preserves existing functionality
- Complete modified files (no placeholders)
- Maintains consistent style and structure
- No missing code segments

### For Error Recovery:
- Automatic error detection and retry
- Specialized debugging instructions
- Common GLSL error patterns included
- Up to 3 attempts to fix compilation issues
- Full context provided to Claude (code + errors)

## Testing

Run the test suite to verify implementation:

```bash
# Test all prompt types
python3 test_prompt_types.py

# Test validation workflow
python3 test_validation.py

# Integration test
python3 -c "from cube.ai import ShaderAgent; agent = ShaderAgent(...)"
```

All tests passing ✅

## Migration Notes

### For Existing Code:
- `generate_shader()` still works with default behavior (generation prompt)
- `refine_shader()` now uses editing prompt automatically
- Add `prompt_type` parameter to use specific prompts
- Use `generate_shader_with_validation()` for automatic error retry

### Breaking Changes:
- None - all changes are backwards compatible
- Old API calls continue to work as before
- New features are opt-in

## Future Enhancements

Potential improvements:
- Configurable max retry attempts
- Custom error patterns per project
- Shader complexity scoring
- Performance optimization hints
- Style consistency checking
