"""
AI Shader Generation Agent - Uses Claude API to generate GLSL shaders.

This module integrates with Claude via the Anthropic API to generate
custom shaders based on natural language descriptions.
"""

import json
import os
import re
import tempfile
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import time
from anthropic import Anthropic


class ShaderGenerationResult:
    """Result of shader generation attempt."""

    def __init__(self, success: bool, shader_path: Optional[Path] = None,
                 error: Optional[str] = None, log: str = ""):
        """
        Initialize result.

        Args:
            success: Whether generation succeeded
            shader_path: Path to generated shader file (if successful)
            error: Error message (if failed)
            log: Full generation log
        """
        self.success = success
        self.shader_path = shader_path
        self.error = error
        self.log = log


class ShaderAgent:
    """
    AI agent for generating GLSL shaders via Claude API.

    Uses Claude via Anthropic API to create shaders
    from natural language descriptions.
    """

    def __init__(self, shaders_dir: Path, examples_root: Optional[Path] = None,
                 validation_renderer=None):
        """
        Initialize shader agent.

        Args:
            shaders_dir: Root shaders directory (agent can only write here)
            examples_root: Root directory containing shader examples (optional)
            validation_renderer: Optional UnifiedRenderer for shader compilation testing
        """
        self.shaders_dir = shaders_dir
        self.shaders_dir.mkdir(parents=True, exist_ok=True)

        # Examples directory (parent of shaders_dir typically)
        self.examples_root = examples_root or shaders_dir.parent

        # Validation renderer for compilation testing
        self.validation_renderer = validation_renderer
        if self.validation_renderer:
            print("✓ Shader validation enabled (using validation renderer)")
        else:
            print("⚠ Shader validation disabled (no validation renderer)")

        # Initialize Anthropic client
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("WARNING: ANTHROPIC_API_KEY not set. Shader generation will fail.")
            print("Set your API key: export ANTHROPIC_API_KEY='your-key-here'")

        self.client = Anthropic(api_key=api_key) if api_key else None
        self.model = "claude-sonnet-4-20250514"  # Latest Claude Sonnet

        # Track last generated shader for iterative refinement
        self.last_shader_path: Optional[Path] = None
        self.conversation_history = []
        self.max_iterations = 3  # Max attempts to fix errors

    def generate_shader(self, user_prompt: str, error_feedback: Optional[str] = None,
                       prompt_type: str = "generation", timeout: int = 120) -> ShaderGenerationResult:
        """
        Generate shader from natural language description.

        Args:
            user_prompt: User's description of desired shader
            error_feedback: Optional error logs from previous attempt
            prompt_type: Type of prompt - "generation", "editing", or "error_fixing"
            timeout: Maximum time to wait for generation (seconds)

        Returns:
            ShaderGenerationResult with outcome
        """
        print(f"\n{'='*60}")
        print(f"AI SHADER {prompt_type.upper()}")
        print(f"{'='*60}")
        print(f"User request: {user_prompt}")
        if error_feedback:
            print(f"Error feedback provided: {len(error_feedback)} chars")
        print(f"{'='*60}\n")

        # Check if client is initialized
        if not self.client:
            error_msg = (
                "Anthropic API client not initialized.\n\n"
                "Please set ANTHROPIC_API_KEY environment variable:\n"
                "export ANTHROPIC_API_KEY='your-key-here'"
            )
            return ShaderGenerationResult(
                success=False,
                error=error_msg,
                log="API key not configured"
            )

        # Find relevant shader examples
        examples = self._find_relevant_examples(user_prompt, max_examples=3)

        # Build appropriate system prompt based on type
        if prompt_type == "error_fixing":
            system_prompt = self._build_error_fixing_prompt(examples)
        elif prompt_type == "editing":
            system_prompt = self._build_editing_prompt(examples)
        else:  # "generation"
            system_prompt = self._build_generation_prompt(examples)

        # Build user message
        user_message = user_prompt
        if error_feedback and prompt_type == "error_fixing":
            # For error fixing, include the error details
            user_message = f"{user_prompt}\n\nCOMPILATION ERROR OUTPUT:\n{error_feedback}"

        # Store in conversation history
        self.conversation_history.append({
            'role': 'user',
            'content': user_message
        })

        try:
            print("Calling Claude API for shader generation...")

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=self.conversation_history
            )

            # Extract response text
            response_text = response.content[0].text

            print(f"Received response ({len(response_text)} chars)")

            # Store assistant response
            self.conversation_history.append({
                'role': 'assistant',
                'content': response_text
            })

            # Extract GLSL code from response
            shader_code = self._extract_shader_code(response_text)

            if not shader_code:
                return ShaderGenerationResult(
                    success=False,
                    error="Could not extract GLSL code from response",
                    log=response_text
                )

            # Generate filename from user prompt
            filename = self._generate_filename(user_prompt)
            shader_path = self.shaders_dir / filename

            # Write shader to file
            print(f"Writing shader to: {shader_path}")
            shader_path.write_text(shader_code)

            # Track for iterative refinement
            self.last_shader_path = shader_path

            print(f"✓ Shader generated successfully: {shader_path.name}\n")

            return ShaderGenerationResult(
                success=True,
                shader_path=shader_path,
                log=response_text
            )

        except Exception as e:
            error_msg = f"Shader generation failed: {str(e)}"
            print(f"✗ {error_msg}\n")

            self.conversation_history.append({
                'role': 'assistant',
                'content': error_msg
            })

            return ShaderGenerationResult(
                success=False,
                error=error_msg,
                log=str(e)
            )

    def generate_shader_with_validation(self, user_prompt: str, ptype: str, timeout: int = 120) -> ShaderGenerationResult:
        """
        Generate shader with automatic compilation error detection and retry.

        This method will:
        1. Generate a shader from the user prompt
        2. Test the shader by attempting to render it
        3. If compilation errors are detected, retry with error feedback
        4. Loop up to 3 times total (1 initial + 2 retries) before giving up

        Args:
            user_prompt: User's description of desired shader
            timeout: Maximum time to wait for generation (seconds)

        Returns:
            ShaderGenerationResult with outcome
        """
        max_attempts = 3
        attempt = 0
        error_feedback = None

        print(f"\n{'='*60}")
        print("SHADER GENERATION WITH VALIDATION")
        print(f"Maximum attempts: {max_attempts}")
        print(f"{'='*60}\n")

        while attempt < max_attempts:
            attempt += 1
            print(f"\n--- Attempt {attempt}/{max_attempts} ---")

            # Determine prompt type based on whether this is a retry
            prompt_type = ptype if attempt == 1 else "error_fixing"

            # Generate shader
            result = self.generate_shader(
                user_prompt,
                error_feedback=error_feedback,
                prompt_type=prompt_type,
                timeout=timeout
            )

            if not result.success:
                print(f"❌ Generation failed: {result.error}")
                return result

            # Test shader compilation
            print(f"\nTesting shader compilation: {result.shader_path.name}")
            has_errors, output = self._test_shader_compilation(result.shader_path)

            if not has_errors:
                print(f"✅ Shader compiled successfully on attempt {attempt}")
                return result

            # Compilation errors detected
            print(f"⚠️  Compilation errors detected")
            print(f"\nError output:")
            print("-" * 60)
            print(output[:1000])  # Show first 1000 chars
            print("-" * 60)

            if attempt >= max_attempts:
                print(f"\n❌ Maximum attempts ({max_attempts}) reached. Giving up.")
                return ShaderGenerationResult(
                    success=False,
                    shader_path=result.shader_path,
                    error=f"Shader failed compilation after {max_attempts} attempts",
                    log=f"Final attempt output:\n{output}"
                )

            # Prepare error feedback for next iteration
            print(f"\nRetrying with error-fixing prompt...")
            error_feedback = self._format_error_feedback(output)

            # For subsequent attempts, include the previous shader code in the prompt
            if result.shader_path and result.shader_path.exists():
                previous_code = result.shader_path.read_text()
                user_prompt = f"Fix the compilation errors in this shader:\n\n```glsl\n{previous_code}\n```"

        # Should never reach here, but just in case
        return result

    def _test_shader_compilation(self, shader_path: Path) -> Tuple[bool, str]:
        """
        Test shader compilation using the validation renderer.

        This uses a dedicated UnifiedRenderer instance that was created on the
        main thread. We must make its OpenGL context current before using it
        from the background thread.

        Args:
            shader_path: Path to shader file to test

        Returns:
            Tuple of (has_errors: bool, output: str)
            has_errors is True if compilation errors detected, False otherwise
        """
        if not self.validation_renderer:
            print("Warning: No validation renderer - skipping validation")
            return False, "No validation renderer - skipping validation"

        try:
            # CRITICAL: Make the validation renderer's context current
            # This is required when calling from a different thread
            if not self.validation_renderer.make_context_current():
                print("Warning: Could not make validation context current - skipping validation")
                return False, "Could not make validation context current"

            # Try to load shader using the validation renderer
            # This will compile the shader and raise an exception if it fails
            self.validation_renderer.load_shader(str(shader_path))

            # Success - shader compiled
            return False, "Shader compiled successfully"

        except Exception as e:
            # Compilation failed - capture full error with traceback
            error_output = (
                f"Shader compilation failed:\n"
                f"{str(e)}\n\n"
                f"Full traceback:\n"
                f"{traceback.format_exc()}"
            )
            return True, error_output

    def _has_compilation_errors(self, output: str) -> bool:
        """
        Check if output contains shader compilation errors.

        Note: This method is now simpler since we get direct compilation errors.

        Args:
            output: Error output from shader compilation

        Returns:
            True if errors detected, False otherwise
        """
        # Since we're directly catching compilation exceptions,
        # we can check for specific error indicators
        if not output:
            return False

        # Common error patterns from direct compilation
        error_patterns = [
            r'compilation error',
            r'ERROR:',
            r'error:',
            r'compilation failed',
            r'GLSL',
            r'syntax error',
            r'undeclared identifier',
            r'Traceback',
        ]

        # Check for any error pattern
        for pattern in error_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return True

        return False

    def _format_error_feedback(self, output: str) -> str:
        """
        Format error output into concise feedback for Claude.

        Args:
            output: Raw output from shader test

        Returns:
            Formatted error feedback
        """
        # Extract the most relevant error lines
        lines = output.split('\n')
        error_lines = []

        for line in lines:
            # Keep lines that look like errors
            if any(keyword in line.lower() for keyword in ['error', 'failed', 'traceback', 'exception']):
                error_lines.append(line.strip())

        if not error_lines:
            # If no specific error lines, just return the whole output (truncated)
            return output[:2000]

        # Return the error lines, limited in size
        error_text = '\n'.join(error_lines)
        if len(error_text) > 2000:
            error_text = error_text[:2000] + "\n... (truncated)"

        return error_text

    def refine_shader(self, refinement_request: str) -> ShaderGenerationResult:
        """
        Refine the last generated shader based on user feedback.

        Args:
            refinement_request: Description of changes to make

        Returns:
            ShaderGenerationResult with updated shader
        """
        if self.last_shader_path is None:
            return ShaderGenerationResult(
                success=False,
                error="No shader to refine. Generate a shader first."
            )

        # Read the current shader code
        current_code = self.last_shader_path.read_text()

        # Build refinement prompt with full shader context
        full_prompt = (
            f"Modify this shader based on the following request: {refinement_request}\n\n"
            f"Current shader ({self.last_shader_path.name}):\n\n"
            f"```glsl\n{current_code}\n```"
        )

        return self.generate_shader(full_prompt, prompt_type="editing")

    def _find_relevant_examples(self, user_prompt: str, max_examples: int = 3) -> list:
        """
        Find relevant shader examples based on user prompt.

        Args:
            user_prompt: User's description
            max_examples: Maximum number of examples to return

        Returns:
            List of (filename, code) tuples
        """
        examples = []

        # Extract keywords from prompt
        keywords = set(re.findall(r'\b[a-z]+\b', user_prompt.lower()))

        # Search in primitives and graphics directories
        search_dirs = [
            self.examples_root / 'primitives',
            self.examples_root / 'graphics'
        ]

        shader_files = []
        for search_dir in search_dirs:
            if search_dir.exists():
                shader_files.extend(search_dir.glob('*.glsl'))

        # Score each shader based on keyword matches
        scored_shaders = []
        for shader_path in shader_files:
            filename = shader_path.stem.lower()
            # Count keyword matches in filename
            score = sum(1 for keyword in keywords if keyword in filename)

            # Bonus for exact matches
            if any(keyword == filename for keyword in keywords):
                score += 10

            if score > 0:
                scored_shaders.append((score, shader_path))

        # Sort by score and take top examples
        scored_shaders.sort(reverse=True, key=lambda x: x[0])

        for score, shader_path in scored_shaders[:max_examples]:
            try:
                code = shader_path.read_text()
                # Truncate very long shaders
                if len(code) > 2000:
                    code = code[:2000] + "\n// ... (truncated)"
                examples.append((shader_path.name, code))
                print(f"Found example: {shader_path.name} (score: {score})")
            except Exception as e:
                print(f"Warning: Could not read {shader_path}: {e}")

        # If no matches, include some basic examples
        if not examples:
            basic_examples = ['sphere.glsl', 'torus.glsl', 'pyramid.glsl']
            for name in basic_examples:
                for search_dir in search_dirs:
                    path = search_dir / name
                    if path.exists():
                        try:
                            code = path.read_text()
                            if len(code) > 2000:
                                code = code[:2000] + "\n// ... (truncated)"
                            examples.append((name, code))
                            print(f"Using basic example: {name}")
                            break
                        except Exception:
                            pass
                if len(examples) >= max_examples:
                    break

        return examples

    def _build_generation_prompt(self, examples: list = None) -> str:
        """
        Build system prompt for initial shader generation.

        Args:
            examples: List of (filename, code) tuples

        Returns:
            System prompt for shader generation
        """
        base_prompt = """You are an expert GLSL shader developer specializing in creating shaders for LED cube visualizations.

Your task is to generate Shadertoy-compatible GLSL shaders based on user requests.

TECHNICAL REQUIREMENTS:
1. Use the standard Shadertoy signature: void mainImage(out vec4 fragColor, in vec2 fragCoord)
2. The shader MUST respond to camera movement using these uniforms:
   - vec3 iCameraPos (camera position)
   - vec3 iCameraRight (camera right vector)
   - vec3 iCameraUp (camera up vector)
   - vec3 iCameraForward (camera forward vector)

   Example ray direction setup:
   vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
   vec3 ro = iCameraPos;
   vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

3. Map configurable parameters to MIDI controls (these are already normalized to 0.0-1.0):
   - float iParam0 - Primary control (e.g., color red, rotation speed, main effect)
   - float iParam1 - Secondary control (e.g., color green, scale, secondary effect)
   - float iParam2 - Tertiary control (e.g., color blue, offset, tertiary effect)
   - float iParam3 - Quaternary control (e.g., shape morphing, complexity)
   - vec4 iParams - All four params as vector (iParam0, iParam1, iParam2, iParam3)

4. Standard Shadertoy uniforms available:
   - vec3 iResolution (viewport resolution in pixels)
   - float iTime (time in seconds)
   - int iFrame (frame counter)

5. For 3D scenes, use raymarching with signed distance functions (SDFs)
6. Include proper lighting (ambient + diffuse + specular)
7. Add clear comments explaining what each iParam controls

CRITICAL - OUTPUT FORMAT:
- You MUST output the COMPLETE .glsl shader file from start to finish
- Include ALL necessary functions: SDFs, lighting, mainImage, etc.
- Do NOT use placeholders like "// ... rest of code" or "// same as before"
- Do NOT omit any part of the shader - output the ENTIRE file
- Start with a comment describing the shader, then output ALL code
- The file should be ready to save as-is and compile immediately

RESPONSE FORMAT:
- Provide ONLY the complete GLSL shader code (no markdown, no explanation text before/after)
- Include a brief comment at the top describing the shader
- Add inline comments explaining iParam mappings
- Ensure the shader is complete and ready to compile

SHADER PATTERNS TO FOLLOW:
- Simple primitives: Use basic SDFs (sphere, box, torus, pyramid)
- Complex effects: Combine multiple SDFs, use domain repetition, fractals
- Colors: Map iParam0-2 to RGB or use them for palette selection
- Animation: Use iTime for movement, iParams for speed/amplitude control
- Camera: Always use the camera uniforms for proper 3D navigation

Your shader should be creative, visually interesting, and fully utilize the MIDI parameters for live control."""

        # Add examples if provided
        if examples:
            base_prompt += "\n\nRELEVANT SHADER EXAMPLES:\n"
            base_prompt += "Study these working examples to understand the format and patterns:\n\n"

            for filename, code in examples:
                base_prompt += f"--- {filename} ---\n"
                base_prompt += code
                base_prompt += "\n\n"

            base_prompt += "Use these examples as reference for structure, SDFs, lighting, and camera setup.\n"
            base_prompt += "Follow the same patterns but create something unique based on the user's request.\n"
            base_prompt += "\nREMEMBER: Output the COMPLETE shader file with ALL code - no omissions or placeholders!\n"

        return base_prompt

    def _build_editing_prompt(self, examples: list = None) -> str:
        """
        Build system prompt for editing/refining existing shaders.

        Args:
            examples: List of (filename, code) tuples

        Returns:
            System prompt for shader editing
        """
        base_prompt = """You are an expert GLSL shader developer specializing in modifying and refining shaders for LED cube visualizations.

Your task is to modify an existing Shadertoy-compatible GLSL shader based on user requests.

The user will provide:
1. The current shader code
2. A description of what changes they want

TECHNICAL REQUIREMENTS (maintain these in edited shader):
1. Use the standard Shadertoy signature: void mainImage(out vec4 fragColor, in vec2 fragCoord)
2. The shader MUST respond to camera movement using these uniforms:
   - vec3 iCameraPos, iCameraRight, iCameraUp, iCameraForward
3. MIDI control parameters (already normalized 0.0-1.0):
   - float iParam0, iParam1, iParam2, iParam3, vec4 iParams
4. Standard uniforms: vec3 iResolution, float iTime, int iFrame
5. For 3D scenes, use raymarching with signed distance functions (SDFs)
6. Include proper lighting (ambient + diffuse + specular)

CRITICAL - OUTPUT FORMAT:
- You MUST output the COMPLETE modified .glsl shader file from start to finish
- Include ALL necessary functions: SDFs, lighting, mainImage, etc.
- Do NOT use placeholders like "// ... rest of code unchanged" or "// same as before"
- Do NOT say "keep the existing X" - actually output X in full
- Even if only changing one line, output the ENTIRE shader file
- The output should be ready to save as-is and compile immediately

RESPONSE FORMAT:
- Provide ONLY the complete modified GLSL shader code (no markdown, no explanation text)
- Include a brief comment at the top describing the shader
- Add inline comments for any new or changed sections
- Ensure the shader is complete and ready to compile

When making modifications:
- Preserve the original style and structure unless changes are requested
- Maintain all existing functionality unless asked to remove it
- Keep iParam mappings consistent unless asked to change them
- Ensure camera controls remain functional

REMEMBER: Output the COMPLETE modified shader file with ALL code - no omissions, shortcuts, or placeholders!"""

        # Add examples if provided
        if examples:
            base_prompt += "\n\nRELEVANT SHADER EXAMPLES:\n"
            base_prompt += "These examples show the expected format and patterns:\n\n"

            for filename, code in examples:
                base_prompt += f"--- {filename} ---\n"
                base_prompt += code
                base_prompt += "\n\n"

            base_prompt += "\nREMEMBER: Output the COMPLETE modified shader file - no omissions!\n"

        return base_prompt

    def _build_error_fixing_prompt(self, examples: list = None) -> str:
        """
        Build system prompt specifically for fixing compilation errors.

        Args:
            examples: List of (filename, code) tuples

        Returns:
            System prompt for error fixing
        """
        base_prompt = """You are an expert GLSL shader developer specializing in debugging and fixing shader compilation errors.

Your task is to fix a shader that failed to compile. The user will provide:
1. The shader code that failed to compile
2. The compilation error output

TECHNICAL REQUIREMENTS (must be present in fixed shader):
1. Use the standard Shadertoy signature: void mainImage(out vec4 fragColor, in vec2 fragCoord)
2. Camera uniforms: vec3 iCameraPos, iCameraRight, iCameraUp, iCameraForward
3. MIDI parameters: float iParam0, iParam1, iParam2, iParam3, vec4 iParams
4. Standard uniforms: vec3 iResolution, float iTime, int iFrame
5. Proper GLSL syntax and function signatures
6. All variables must be declared before use
7. All functions must be defined before being called

CRITICAL - OUTPUT FORMAT:
- You MUST output the COMPLETE fixed .glsl shader file from start to finish
- Include ALL necessary functions: SDFs, lighting, mainImage, helper functions, etc.
- Do NOT use placeholders like "// ... rest unchanged" or "// fix the error here"
- Do NOT say "the rest remains the same" - actually output ALL code
- Even if fixing one error, output the ENTIRE corrected shader file
- The output should be ready to save as-is and compile immediately

RESPONSE FORMAT:
- Provide ONLY the complete fixed GLSL shader code (no markdown, no explanation text)
- Include a brief comment at the top describing the shader
- Add a comment near the fix explaining what was wrong
- Ensure the shader is complete and ready to compile

COMMON GLSL ERRORS TO FIX:
- Undeclared identifiers - add missing variable declarations
- Function signature mismatches - correct parameter types
- Missing semicolons - add them
- Type mismatches - add proper type casts
- Undefined functions - implement or remove calls
- Syntax errors - correct GLSL syntax
- Missing uniform declarations - add them
- Wrong function return types - correct them

DEBUGGING APPROACH:
1. Read the error message carefully - it tells you the line number and issue
2. Identify the root cause (missing declaration, wrong type, syntax error, etc.)
3. Fix the error and any related issues
4. Ensure all dependent code still works
5. Output the COMPLETE fixed shader

REMEMBER: Output the ENTIRE fixed shader file with ALL code - no omissions, shortcuts, or placeholders!
The shader must be compilable as-is."""

        # Add examples if provided
        if examples:
            base_prompt += "\n\nRELEVANT WORKING SHADER EXAMPLES:\n"
            base_prompt += "These are examples of working shaders for reference:\n\n"

            for filename, code in examples:
                base_prompt += f"--- {filename} ---\n"
                base_prompt += code
                base_prompt += "\n\n"

            base_prompt += "\nUse these examples to understand correct syntax, structure, and patterns.\n"
            base_prompt += "\nREMEMBER: Output the COMPLETE fixed shader file - no omissions!\n"

        return base_prompt

    def _extract_shader_code(self, response_text: str) -> Optional[str]:
        """
        Extract GLSL shader code from Claude's response.

        Args:
            response_text: Full response from Claude

        Returns:
            Extracted shader code, or None if not found
        """
        # Try to find code block with glsl marker
        pattern = r'```(?:glsl)?\s*(.*?)```'
        matches = re.findall(pattern, response_text, re.DOTALL)

        if matches:
            # Return the first (or longest) code block
            code = max(matches, key=len).strip()
            return code

        # If no code block found, check if entire response is code
        # (Claude might output raw code without markdown)
        if 'void mainImage' in response_text:
            # Clean up any leading/trailing explanation text
            lines = response_text.split('\n')
            start_idx = 0
            end_idx = len(lines)

            # Find where the shader code starts
            for i, line in enumerate(lines):
                if 'void mainImage' in line or '//' in line or 'float' in line:
                    start_idx = i
                    break

            # Extract from start to end
            shader_lines = lines[start_idx:end_idx]
            return '\n'.join(shader_lines).strip()

        return None

    def _generate_filename(self, user_prompt: str) -> str:
        """
        Generate a descriptive filename from user prompt.

        Args:
            user_prompt: User's prompt text

        Returns:
            Safe filename with .glsl extension
        """
        # Check if this is an editing prompt with existing filename
        # Pattern: "I'm editing the shader 'filename.glsl'"
        edit_match = re.search(r"editing.*?shader\s+['\"]([a-zA-Z0-9_]+)\.glsl['\"]", user_prompt, re.IGNORECASE)
        if edit_match:
            # Preserve the original filename for edits
            original_name = edit_match.group(1)
            # Use temp suffix to avoid overwriting during generation
            return f"{original_name}_edit_temp.glsl"

        # Extract key words from prompt
        words = re.findall(r'\b[a-zA-Z]+\b', user_prompt.lower())

        # Remove common words and editing-related words
        stop_words = {'a', 'an', 'the', 'with', 'for', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from',
                      'create', 'make', 'generate', 'shader', 'effect', 'that', 'is', 'are', 'be', 'have',
                      'of', 'it', 'its', 'by', 'as', 'has', 'was', 'this', 'should', 'would', 'could',
                      'rotating', 'pulsing', 'changing', 'moving',
                      # Editing-related words to skip
                      'i', 'm', 'editing', 'current', 'code', 'glsl', 'modification', 'request',
                      'can', 'you', 'please', 'one', 'each', 'parameter', 'control', 'size', 'prism', 'prisms'}
        meaningful_words = [w for w in words if w not in stop_words]

        # Take first 1-2 meaningful words only for shorter names
        filename_parts = meaningful_words[:2]

        if not filename_parts:
            # Fallback to timestamp
            filename_parts = [f"shader_{int(time.time())}"]

        # Join with underscores
        base_name = '_'.join(filename_parts)

        # Make filename unique if it already exists
        filename = f"{base_name}.glsl"
        counter = 1
        while (self.shaders_dir / filename).exists():
            filename = f"{base_name}_{counter}.glsl"
            counter += 1

        return filename

    def get_conversation_history(self) -> str:
        """
        Get formatted conversation history for display.

        Returns:
            Formatted conversation string
        """
        lines = []
        for entry in self.conversation_history:
            role = entry['role'].upper()
            content = entry['content']
            lines.append(f"{role}: {content}")
            lines.append("")

        return '\n'.join(lines)

    def clear_history(self):
        """Clear conversation history and reset agent."""
        self.conversation_history = []
        self.last_shader_path = None
