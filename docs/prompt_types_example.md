# Shader Agent Prompt Types - Complete Example

This document shows how the three specialized system prompts work together in the shader generation workflow.

## The Three Prompt Types

### 1. Generation Prompt
**When used**: Initial shader creation from user description
**Focus**: Creativity, visual interest, and following shader patterns
**Key instruction**: "Output the COMPLETE .glsl shader file from start to finish"

### 2. Editing Prompt
**When used**: Refining or modifying an existing shader
**Focus**: Preserving structure while making requested changes
**Key instruction**: "Even if only changing one line, output the ENTIRE shader file"

### 3. Error Fixing Prompt
**When used**: Fixing compilation errors in a failed shader
**Focus**: Debugging, identifying root causes, and fixing GLSL errors
**Key instruction**: "Even if fixing one error, output the ENTIRE corrected shader file"

## Complete Workflow Example

### Scenario: User asks for "a pulsing red sphere"

#### Attempt 1: Generation Prompt
```
System Prompt: GENERATION
User Message: "Create a pulsing red sphere"

Response: [Complete shader code with 150 lines]
Result: Shader compiles ✅
Status: SUCCESS - Return shader to user
```

### Scenario: User asks for "a rotating cube with gradient colors"

#### Attempt 1: Generation Prompt
```
System Prompt: GENERATION
User Message: "Create a rotating cube with gradient colors"

Response: [Complete shader code with 200 lines]
Test Result: ❌ ERROR: undeclared identifier: gradientColor at line 45
Status: RETRY with error fixing prompt
```

#### Attempt 2: Error Fixing Prompt
```
System Prompt: ERROR_FIXING
User Message: "Fix the compilation errors in this shader:

```glsl
// [Full 200 lines of previous shader code]
```

COMPILATION ERROR OUTPUT:
ERROR: undeclared identifier: gradientColor at line 45
"

Response: [Complete fixed shader code with 200 lines, now declares gradientColor]
Test Result: ✅ Compiles successfully
Status: SUCCESS - Return fixed shader to user
```

### Scenario: User wants to modify an existing shader

#### Using Editing Prompt
```
System Prompt: EDITING
User Message: "Modify this shader based on the following request: Make it pulse faster

Current shader (pulsing_sphere.glsl):

```glsl
// [Full shader code - 150 lines]
```"

Response: [Complete modified shader with faster pulse timing]
Result: Shader compiles ✅
Status: SUCCESS - Return modified shader
```

## Key Differences in Prompt Content

### Generation Prompt Emphasizes:
```
Your shader should be creative, visually interesting, and fully utilize
the MIDI parameters for live control.

SHADER PATTERNS TO FOLLOW:
- Simple primitives: Use basic SDFs
- Complex effects: Combine multiple SDFs
- Colors: Map iParam0-2 to RGB
- Animation: Use iTime for movement
```

### Editing Prompt Emphasizes:
```
When making modifications:
- Preserve the original style and structure unless changes are requested
- Maintain all existing functionality unless asked to remove it
- Keep iParam mappings consistent unless asked to change them

Do NOT say "keep the existing X" - actually output X in full
```

### Error Fixing Prompt Emphasizes:
```
COMMON GLSL ERRORS TO FIX:
- Undeclared identifiers - add missing variable declarations
- Function signature mismatches - correct parameter types
- Type mismatches - add proper type casts

DEBUGGING APPROACH:
1. Read the error message carefully - it tells you the line number and issue
2. Identify the root cause (missing declaration, wrong type, syntax error, etc.)
3. Fix the error and any related issues
4. Ensure all dependent code still works
5. Output the COMPLETE fixed shader
```

## Why This Matters

### Without Specialized Prompts:
- Claude might use placeholders: `// ... rest of code unchanged`
- May not focus on the specific task (generation vs debugging)
- Error messages might not provide enough context for fixes
- Editing might lose important existing functionality

### With Specialized Prompts:
- ✅ Always outputs complete, compilable shader code
- ✅ Focuses on the specific task at hand
- ✅ Error fixing has debugging context and common error patterns
- ✅ Editing preserves existing structure and functionality
- ✅ Generation emphasizes creativity and best practices

## Usage in Code

```python
from cube.ai import ShaderAgent
from pathlib import Path

agent = ShaderAgent(Path('shaders/generated'))

# Automatic workflow with validation (uses generation → error_fixing prompts)
result = agent.generate_shader_with_validation("Create a rotating torus")

# Manual usage with specific prompt types
result = agent.generate_shader(
    "Create a sphere",
    prompt_type="generation"  # Default
)

result = agent.generate_shader(
    "Modify this shader: ...",
    prompt_type="editing"
)

result = agent.generate_shader(
    "Fix this shader: ...",
    error_feedback="ERROR: ...",
    prompt_type="error_fixing"
)

# Convenience method for editing (automatically uses editing prompt)
result = agent.refine_shader("Make it spin faster")
```

## Summary

The three-prompt system ensures:
1. **Complete file output** - No placeholders or omissions
2. **Task-specific guidance** - Each prompt optimized for its purpose
3. **Better error recovery** - Error fixing prompt includes debugging strategies
4. **Consistent quality** - All outputs are compilable shader files
5. **Iterative refinement** - Editing prompt preserves existing functionality
