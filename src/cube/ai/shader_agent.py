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

from .shader_prompts import (
    GENERATION_PROMPT,
    EDITING_PROMPT,
    ERROR_FIXING_PROMPT,
    format_prompt_with_examples
)


class ShaderGenerationResult:
    """Result of shader generation attempt."""

    def __init__(self, success: bool, shader_path: Optional[Path] = None,
                 error: Optional[str] = None):
        """
        Initialize result.

        Args:
            success: Whether generation succeeded
            shader_path: Path to generated shader file (if successful)
            error: Error message (if failed)
        """
        self.success = success
        self.shader_path = shader_path
        self.error = error


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
                "Please set ANTHROPIC_API_KEY environment variable:\n"
                "export ANTHROPIC_API_KEY='your-key-here'"
            )
            return ShaderGenerationResult(
                success=False,
                error=error_msg
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
                    error="Could not extract GLSL code from response"
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
                error=error_msg
            )

    def generate_shader_with_validation(self, user_prompt: str, ptype: str,
                                        existing_shader_path: Optional[Path] = None,
                                        timeout: int = 120) -> ShaderGenerationResult:
        """
        Generate shader with automatic compilation error detection and retry.

        New workflow:
        1. Generate shader code (no file written yet)
        2. Write to temp file for validation
        3. Test compilation on temp file
        4. If successful: commit temp to final file
        5. If failed: retry up to 3 times, cleanup temp files

        Args:
            user_prompt: User's description of desired shader
            ptype: Prompt type - "generation" or "editing"
            existing_shader_path: For edits, path to existing shader file
            timeout: Maximum time to wait for generation (seconds)

        Returns:
            ShaderGenerationResult with outcome
        """
        max_attempts = 3
        attempt = 0
        error_feedback = None
        suggested_filename = None
        temp_files = []  # Track all temp files for cleanup
        original_user_prompt = user_prompt  # Save original for example finding

        is_edit = ptype == "editing" and existing_shader_path is not None

        print(f"\n{'='*60}")
        print(
            f"SHADER {'EDITING' if is_edit else 'GENERATION'} WITH VALIDATION")
        if is_edit:
            print(f"Editing: {existing_shader_path.name}")
        print(f"Maximum attempts: {max_attempts}")
        print(f"{'='*60}\n")

        # Check if client is initialized
        if not self.client:
            error_msg = (
                "Please set ANTHROPIC_API_KEY environment variable:\n"
                "export ANTHROPIC_API_KEY='your-key-here'"
            )
            return ShaderGenerationResult(
                success=False,
                error=error_msg
            )

        while attempt < max_attempts:
            attempt += 1
            print(f"\n--- Attempt {attempt}/{max_attempts} ---")

            # Determine prompt type based on whether this is a retry
            prompt_type = ptype if attempt == 1 else "error_fixing"

            # Generate shader CODE (don't write file yet)
            print("Calling Claude API...")
            try:
                # Call Claude API directly without writing files
                # Use original_user_prompt for finding relevant examples (not the modified retry prompt)
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self._build_prompt_for_type(
                        prompt_type, ptype, original_user_prompt),
                    messages=self.conversation_history + [{
                        'role': 'user',
                        'content': user_prompt if not error_feedback else f"{user_prompt}\n\nCOMPILATION ERROR OUTPUT:\n{error_feedback}"
                    }]
                )

                response_text = response.content[0].text
                print(f"Received response ({len(response_text)} chars)")

                # Extract shader code
                shader_code = self._extract_shader_code(response_text)
                if not shader_code:
                    return ShaderGenerationResult(
                        success=False,
                        error="Could not extract GLSL code from response"
                    )

                # Determine filename to use
                if is_edit:
                    # For edits: use existing file's name
                    suggested_filename = existing_shader_path.name
                elif attempt == 1:
                    # For new generations (first attempt): extract from LLM response
                    suggested_filename = self._extract_filename(response_text)
                    if not suggested_filename:
                        # Fallback to auto-generated name
                        suggested_filename = self._generate_filename(user_prompt)
                        print(f"Warning: No filename suggested by LLM, using: {suggested_filename}")
                    else:
                        print(f"LLM suggested filename: {suggested_filename}")
                # else: For retries (attempt 2+), keep using suggested_filename from attempt 1

                # Determine temp file path
                # Always create a temp file based on the suggested filename, adding _tmp before extension
                base_name = Path(suggested_filename).stem
                ext = Path(suggested_filename).suffix or ".glsl"
                temp_path = self.shaders_dir / f"{base_name}_tmp{ext}"

                # Write shader code to temp file
                print(f"Writing to temp file: {temp_path.name}")
                temp_path.write_text(shader_code)
                temp_files.append(temp_path)

                # Test shader compilation on temp file
                print(f"Testing compilation...")
                has_errors, compilation_test_output = self._test_shader_compilation(temp_path)

                if not has_errors:
                    print(
                        f"✅ Shader compiled successfully on attempt {attempt}")

                    # Determine final file path
                    if is_edit:
                        # For edits: overwrite the original file
                        final_path = existing_shader_path
                        print(
                            f"Committing to original file: {final_path.name}")
                        final_path.write_text(shader_code)
                    else:
                        # For new generation: use suggested filename
                        final_path = self.shaders_dir / suggested_filename
                        print(f"Writing final shader: {final_path.name}")
                        final_path.write_text(shader_code)

                    # Clean up all temp files
                    for temp_file in temp_files:
                        if temp_file.exists():
                            try:
                                temp_file.unlink()
                                print(
                                    f"🗑️  Cleaned up temp file: {temp_file.name}")
                            except Exception as e:
                                print(
                                    f"Warning: Could not delete temp file: {e}")

                    return ShaderGenerationResult(
                        success=True,
                        shader_path=final_path
                    )

                # Compilation errors detected
                print(f"⚠️  Compilation errors detected")
                print(f"\nError output:")
                print("-" * 60)
                print(compilation_test_output[:1000])  # Show first 1000 chars
                print("-" * 60)

                if attempt >= max_attempts:
                    print(
                        f"\n❌ Maximum attempts ({max_attempts}) reached. Giving up.")
                    break  # Exit loop to cleanup

                # Prepare for retry
                print(f"\nRetrying with error-fixing prompt...")
                error_feedback = compilation_test_output
                user_prompt = f"Fix the compilation errors in this shader:\n\n```glsl\n{shader_code}\n```"

            except Exception as e:
                error_msg = f"Shader generation failed: {str(e)}"
                print(f"❌ {error_msg}")

                # Clean up temp files on exception
                for temp_file in temp_files:
                    if temp_file.exists():
                        try:
                            temp_file.unlink()
                        except:
                            pass

                return ShaderGenerationResult(
                    success=False,
                    error=error_msg
                )

        # Max attempts reached - cleanup all temp files
        print("\n🗑️  Cleaning up all temp files...")
        for temp_file in temp_files:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                    print(f"   Deleted: {temp_file.name}")
                except Exception as e:
                    print(
                        f"   Warning: Could not delete {temp_file.name}: {e}")

        return ShaderGenerationResult(
            success=False,
            error=f"Shader failed compilation after {max_attempts} attempts"
        )

    def _build_prompt_for_type(self, prompt_type: str, original_type: str, user_prompt: str = "") -> str:
        """
        Helper to get the right system prompt with examples.

        Args:
            prompt_type: Current prompt type ("generation", "editing", "error_fixing")
            original_type: Original request type (for context)
            user_prompt: User's prompt (for finding relevant examples)

        Returns:
            Complete system prompt with examples
        """
        # Find relevant examples for first attempt
        examples = self._find_relevant_examples(
            user_prompt, max_examples=3) if user_prompt else []

        if prompt_type == "error_fixing":
            return self._build_error_fixing_prompt(examples)
        elif original_type == "editing":
            return self._build_editing_prompt(examples)
        else:
            return self._build_generation_prompt(examples)

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
                print(
                    "Warning: Could not make validation context current - skipping validation")
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
        return format_prompt_with_examples(GENERATION_PROMPT, examples or [])

    def _build_editing_prompt(self, examples: list = None) -> str:
        """
        Build system prompt for editing/refining existing shaders.

        Args:
            examples: List of (filename, code) tuples

        Returns:
            System prompt for shader editing
        """
        return format_prompt_with_examples(EDITING_PROMPT, examples or [])

    def _build_error_fixing_prompt(self, examples: list = None) -> str:
        """
        Build system prompt specifically for fixing compilation errors.

        Args:
            examples: List of (filename, code) tuples

        Returns:
            System prompt for error fixing
        """
        return format_prompt_with_examples(ERROR_FIXING_PROMPT, examples or [])

    def _extract_shader_code(self, response_text: str) -> Optional[str]:
        """
        Extract GLSL shader code from Claude's response.

        For new generations, this extracts just the code (filename is extracted separately).
        For edits/fixes, this extracts the entire response as code.

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

            # Find where the shader code starts (skip FILENAME line if present)
            for i, line in enumerate(lines):
                if line.startswith('FILENAME:'):
                    start_idx = i + 1  # Start after filename line
                    continue
                if 'void mainImage' in line or '//' in line or ('float' in line and '(' in line):
                    start_idx = i
                    break

            # Extract from start to end
            shader_lines = lines[start_idx:end_idx]
            return '\n'.join(shader_lines).strip()

        return None

    def _extract_filename(self, response_text: str) -> Optional[str]:
        """
        Extract filename suggestion from Claude's response for new generations.

        Args:
            response_text: Full response from Claude

        Returns:
            Extracted filename (e.g., "spiral_tunnel.glsl"), or None if not found
        """
        # Look for FILENAME: pattern at start of response
        lines = response_text.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            if line.startswith('FILENAME:'):
                # Extract filename after colon
                filename = line.split(':', 1)[1].strip()
                # Validate filename format
                if filename.endswith('.glsl') and re.match(r'^[a-z0-9_]+\.glsl$', filename):
                    return filename
                else:
                    print(f"Warning: Invalid filename format: {filename}")
                    break

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
        edit_match = re.search(
            r"editing.*?shader\s+['\"]([a-zA-Z0-9_]+)\.glsl['\"]", user_prompt, re.IGNORECASE)
        if edit_match:
            # Preserve the original filename for edits
            original_name = edit_match.group(1)
            # Use temp suffix to avoid overwriting during generation
            return f"{original_name}_edit_temp.glsl"

        return f"shader_{int(time.time())}.glsl"

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
