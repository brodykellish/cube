"""
Shader compilation utilities for testing and loading Shadertoy-format shaders.

This module provides shared functionality for wrapping and compiling shaders
that can be used by both the renderer and the AI agent.
"""

import traceback
from pathlib import Path
from typing import Tuple, Optional

try:
    from OpenGL.GL import *
    from OpenGL.GL import shaders
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False


def wrap_shadertoy_shader(fragment_source: str, glsl_version: str = "120",
                          precision_statement: str = "") -> Tuple[str, str]:
    """
    Wrap a Shadertoy-format shader with uniforms and helper functions.

    Args:
        fragment_source: Raw shader source code (must contain mainImage function)
        glsl_version: GLSL version string (e.g., "120", "300 es", "330 core")
        precision_statement: Precision statement for mobile (e.g., "precision mediump float;")

    Returns:
        Tuple of (vertex_source, fragment_wrapped)
    """
    # Determine if we're using modern GLSL (ES 3.00+ or desktop 3.30+)
    is_modern = glsl_version not in ["100", "120"]

    # Modern GLSL uses 'in'/'out', legacy uses 'attribute'/'varying'
    attribute_keyword = "in" if is_modern else "attribute"

    vertex_source = f"""#version {glsl_version}
{attribute_keyword} vec2 position;
void main() {{
    gl_Position = vec4(position, 0.0, 1.0);
}}
"""

    # Modern GLSL requires explicit output declaration
    frag_output_decl = "out vec4 fragColor;" if is_modern else ""
    frag_color_target = "fragColor" if is_modern else "gl_FragColor"

    # Modern GLSL has texture() built-in, legacy needs texture2D()
    texture_define = "" if is_modern else "#define texture texture2D"

    # Modern GLSL has tanh() and round() built-in, legacy needs polyfills
    helper_functions = "" if is_modern else """
float tanh(float x) {
    float e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}

vec2 tanh(vec2 x) {
    vec2 e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}

vec3 tanh(vec3 x) {
    vec3 e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}

vec4 tanh(vec4 x) {
    vec4 e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}

float round(float x) {
    return floor(x + 0.5);
}

vec2 round(vec2 x) {
    return floor(x + 0.5);
}

vec3 round(vec3 x) {
    return floor(x + 0.5);
}

vec4 round(vec4 x) {
    return floor(x + 0.5);
}
"""

    fragment_wrapped = f"""#version {glsl_version}
{precision_statement}
{frag_output_decl}
uniform vec3 iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int iFrame;
uniform vec4 iMouse;
uniform vec4 iInput;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform sampler2D iChannel2;
uniform sampler2D iChannel3;
uniform vec3 iCameraPos;
uniform vec3 iCameraRight;
uniform vec3 iCameraUp;
uniform vec3 iCameraForward;
uniform float iBPM;
uniform float iBeatPhase;
uniform float iBeatPulse;
uniform float iAudioLevel;
uniform vec4 iAudioSpectrum;
uniform float iDebugAxes;
uniform float iParam0;
uniform float iParam1;
uniform float iParam2;
uniform float iParam3;
uniform vec4 iParams;

{texture_define}
{helper_functions}
{fragment_source}

void main() {{
    mainImage({frag_color_target}, gl_FragCoord.xy);
}}
"""

    return vertex_source, fragment_wrapped


def test_shader_compilation(shader_path: Path, glsl_version: str = "120",
                            precision_statement: str = "") -> Tuple[bool, str]:
    """
    Test if a shader compiles successfully without rendering it.

    Note: This requires an active OpenGL context. If no context is available,
    validation is skipped.

    Args:
        shader_path: Path to shader file
        glsl_version: GLSL version string
        precision_statement: Precision statement for mobile

    Returns:
        Tuple of (has_errors: bool, output: str)
        - has_errors: True if compilation failed
        - output: Error message if failed, success message otherwise
    """
    if not OPENGL_AVAILABLE:
        return False, "OpenGL not available - skipping validation"

    # Check if we have an active OpenGL context
    try:
        # Try to get the current context - this will fail if no context exists
        from OpenGL.GL import glGetString, GL_VERSION
        version = glGetString(GL_VERSION)
        if version is None:
            # No active context
            return False, "No active OpenGL context - skipping validation"
    except Exception:
        # No context available
        return False, "No active OpenGL context - skipping validation"

    try:
        # Read shader source
        fragment_source = shader_path.read_text()

        # Wrap shader
        vertex_source, fragment_wrapped = wrap_shadertoy_shader(
            fragment_source, glsl_version, precision_statement
        )

        # Try to compile
        try:
            vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
            program = shaders.compileProgram(vertex_shader, fragment_shader)

            # Cleanup
            glDeleteProgram(program)
            glDeleteShader(vertex_shader)
            glDeleteShader(fragment_shader)

            return False, "Shader compiled successfully"

        except Exception as compile_error:
            # Compilation failed - capture full error with traceback
            error_output = (
                f"Shader compilation failed:\n"
                f"{str(compile_error)}\n\n"
                f"Full traceback:\n"
                f"{traceback.format_exc()}"
            )
            return True, error_output

    except Exception as e:
        # Error reading or processing shader file
        error_output = (
            f"Error testing shader:\n"
            f"{str(e)}\n\n"
            f"Full traceback:\n"
            f"{traceback.format_exc()}"
        )
        return True, error_output


def test_shader_source_compilation(fragment_source: str, glsl_version: str = "120",
                                   precision_statement: str = "") -> Tuple[bool, str]:
    """
    Test if shader source code compiles successfully without saving to file.

    Note: This requires an active OpenGL context. If no context is available,
    validation is skipped.

    Args:
        fragment_source: Raw shader source code
        glsl_version: GLSL version string
        precision_statement: Precision statement for mobile

    Returns:
        Tuple of (has_errors: bool, output: str)
        - has_errors: True if compilation failed
        - output: Error message if failed, success message otherwise
    """
    if not OPENGL_AVAILABLE:
        return False, "OpenGL not available - skipping validation"

    # Check if we have an active OpenGL context
    try:
        # Try to get the current context - this will fail if no context exists
        from OpenGL.GL import glGetString, GL_VERSION
        version = glGetString(GL_VERSION)
        if version is None:
            # No active context
            return False, "No active OpenGL context - skipping validation"
    except Exception:
        # No context available
        return False, "No active OpenGL context - skipping validation"

    try:
        # Wrap shader
        vertex_source, fragment_wrapped = wrap_shadertoy_shader(
            fragment_source, glsl_version, precision_statement
        )

        # Try to compile
        try:
            vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
            program = shaders.compileProgram(vertex_shader, fragment_shader)

            # Cleanup
            glDeleteProgram(program)
            glDeleteShader(vertex_shader)
            glDeleteShader(fragment_shader)

            return False, "Shader compiled successfully"

        except Exception as compile_error:
            # Compilation failed - capture full error with traceback
            error_output = (
                f"Shader compilation failed:\n"
                f"{str(compile_error)}\n\n"
                f"Full traceback:\n"
                f"{traceback.format_exc()}"
            )
            return True, error_output

    except Exception as e:
        # Error processing shader
        error_output = (
            f"Error testing shader:\n"
            f"{str(e)}\n\n"
            f"Full traceback:\n"
            f"{traceback.format_exc()}"
        )
        return True, error_output
