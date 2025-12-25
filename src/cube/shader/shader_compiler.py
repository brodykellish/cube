"""
Shader compilation utilities for testing and loading Shadertoy-format shaders.

This module provides shared functionality for wrapping and compiling shaders
that can be used by both the renderer and the AI agent.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Tuple

try:
    # Import OpenGL lazily but record availability so callers can
    # short‑circuit when running in environments without GL.
    from OpenGL.GL import (  # type: ignore[import-untyped]
        GL_FRAGMENT_SHADER,
        GL_VERTEX_SHADER,
        GL_VERSION,
        glDeleteProgram,
        glDeleteShader,
        glGetString,
    )
    from OpenGL.GL import shaders  # type: ignore[import-untyped]

    OPENGL_AVAILABLE = True
except Exception:  # ImportError or driver errors
    shaders = None  # type: ignore[assignment]
    OPENGL_AVAILABLE = False


def wrap_shadertoy_shader(
    fragment_source: str,
    glsl_version: str = "120",
    precision_statement: str = "",
) -> Tuple[str, str]:
    """
    Wrap a Shadertoy-format shader with uniforms and helper functions.

    Args:
        fragment_source: Raw shader source code (must contain mainImage function)
        glsl_version: GLSL version string (e.g., "120", "300 es", "330 core")
        precision_statement: Precision statement for mobile (e.g., "precision mediump float;")

    Returns:
        Tuple of (vertex_source, fragment_wrapped)
    """
    is_modern = glsl_version not in ("100", "120")
    attribute_keyword = "in" if is_modern else "attribute"

    vertex_source = (
        f"#version {glsl_version}\n"
        f"{attribute_keyword} vec2 position;\n"
        "void main() {\n"
        "    gl_Position = vec4(position, 0.0, 1.0);\n"
        "}\n"
    )

    frag_output_decl = "out vec4 fragColor;" if is_modern else ""
    frag_color_target = "fragColor" if is_modern else "gl_FragColor"

    texture_define = "" if is_modern else "#define texture texture2D"
    helper_functions = (
        ""
        if is_modern
        else """
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
    )

    fragment_wrapped = (
        f"#version {glsl_version}\n"
        f"{precision_statement}\n"
        f"{frag_output_decl}\n"
        "uniform vec3 iResolution;\n"
        "uniform float iTime;\n"
        "uniform float iTimeDelta;\n"
        "uniform int iFrame;\n"
        "uniform vec4 iMouse;\n"
        "uniform vec4 iInput;\n"
        "uniform sampler2D iChannel0;\n"
        "uniform sampler2D iChannel1;\n"
        "uniform sampler2D iChannel2;\n"
        "uniform sampler2D iChannel3;\n"
        "uniform vec3 iCameraPos;\n"
        "uniform vec3 iCameraRight;\n"
        "uniform vec3 iCameraUp;\n"
        "uniform vec3 iCameraForward;\n"
        "uniform float iBPM;\n"
        "uniform float iBeatPhase;\n"
        "uniform float iBeatPulse;\n"
        "uniform float iAudioLevel;\n"
        "uniform vec4 iAudioSpectrum;\n"
        "uniform float iDebugAxes;\n"
        "uniform float iParam0;\n"
        "uniform float iParam1;\n"
        "uniform float iParam2;\n"
        "uniform float iParam3;\n"
        "uniform float iParam4;\n"
        "uniform float iParam5;\n"
        "uniform float iParam6;\n"
        "uniform float iParam7;\n"
        "\n"
        f"{texture_define}\n"
        f"{helper_functions}\n"
        f"{fragment_source}\n"
        "\n"
        "void main() {\n"
        f"    mainImage({frag_color_target}, gl_FragCoord.xy);\n"
        "}\n"
    )

    return vertex_source, fragment_wrapped


def _has_active_context() -> bool:
    """
    Return True if an OpenGL context appears to be current.

    This uses ``glGetString(GL_VERSION)`` which returns ``None`` when no
    context is bound on the calling thread for PyOpenGL.
    """
    if not OPENGL_AVAILABLE:
        return False
    try:
        version = glGetString(GL_VERSION)
    except Exception:
        return False
    return bool(version)


def _ensure_validation_context() -> bool:
    """
    Ensure an OpenGL context is current for validation.
    
    Tries to use the shared pyglet window from PygletShaderRendererFBO if available,
    otherwise creates a minimal context.
    
    Returns True if context is current, False otherwise.
    """
    if not OPENGL_AVAILABLE:
        return False
    
    # Check if we already have an active context
    if _has_active_context():
        return True
    
    # Try to use shared pyglet window if available
    try:
        from cube.shader.shader_renderer_pyglet_fbo import PygletShaderRendererFBO
        if PygletShaderRendererFBO._shared_window:
            PygletShaderRendererFBO._shared_window.switch_to()
            return True
    except Exception:
        pass
    
    # Try to create a minimal validation context
    try:
        import pyglet
        # Create a minimal hidden window for validation
        # This will be cleaned up when the process exits
        if not hasattr(_ensure_validation_context, '_validation_window'):
            _ensure_validation_context._validation_window = pyglet.window.Window(
                width=64,
                height=64,
                caption="Shader Validation Context",
                visible=False,
            )
        _ensure_validation_context._validation_window.switch_to()
        # Verify context is now active
        return _has_active_context()
    except Exception:
        return False


def test_shader_compilation(
    shader_path: Path,
    glsl_version: str = "120",
    precision_statement: str = "",
) -> Tuple[bool, str]:
    """
    Test if a shader file compiles successfully without rendering it.

    Returns ``(has_errors, output)`` where:
    - ``has_errors`` is True when compilation failed
    - ``output`` contains an informational or error message

    If OpenGL is not available or no context can be made current, validation is skipped
    and ``has_errors`` is False so callers can treat it as non-fatal.
    """
    if not OPENGL_AVAILABLE:
        return False, "OpenGL not available - skipping validation"

    # Ensure we have a context for compilation
    if not _ensure_validation_context():
        return False, "No OpenGL context available - skipping validation"

    try:
        fragment_source = shader_path.read_text()
        vertex_source, fragment_wrapped = wrap_shadertoy_shader(
            fragment_source,
            glsl_version,
            precision_statement,
        )
    except Exception as e:
        error_output = (
            "Error testing shader:\n"
            f"{e}\n\n"
            "Full traceback:\n"
            f"{traceback.format_exc()}"
        )
        return True, error_output

    try:
        vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
        fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
        program = shaders.compileProgram(vertex_shader, fragment_shader)
        glDeleteProgram(program)
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        return False, "Shader compiled successfully"
    except Exception as compile_error:
        error_output = (
            "Shader compilation failed:\n"
            f"{compile_error}\n\n"
            "Full traceback:\n"
            f"{traceback.format_exc()}"
        )
        return True, error_output


def test_shader_source_compilation(
    fragment_source: str,
    glsl_version: str = "120",
    precision_statement: str = "",
) -> Tuple[bool, str]:
    """
    Test if shader source code compiles successfully without saving to file.

    Behavior is the same as :func:`test_shader_compilation` but operates on a
    source string instead of a file path.
    """
    if not OPENGL_AVAILABLE:
        return False, "OpenGL not available - skipping validation"

    if not _has_active_context():
        return False, "No active OpenGL context - skipping validation"

    try:
        vertex_source, fragment_wrapped = wrap_shadertoy_shader(
            fragment_source,
            glsl_version,
            precision_statement,
        )
    except Exception as e:
        error_output = (
            "Error testing shader:\n"
            f"{e}\n\n"
            "Full traceback:\n"
            f"{traceback.format_exc()}"
        )
        return True, error_output

    try:
        vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
        fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
        program = shaders.compileProgram(vertex_shader, GL_VERTEX_SHADER, fragment_shader)
        glDeleteProgram(program)
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        return False, "Shader compiled successfully"
    except Exception as compile_error:
        error_output = (
            "Shader compilation failed:\n"
            f"{compile_error}\n\n"
            "Full traceback:\n"
            f"{traceback.format_exc()}"
        )
        return True, error_output