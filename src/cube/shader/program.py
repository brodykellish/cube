# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/program.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-22 20:44:34 UTC (1766436274)

"""Shader program wrapper for cube using Shadertoy‑style fragments."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from OpenGL.GL import (  # type: ignore[import-untyped]
    GL_ACTIVE_UNIFORMS,
    GL_FRAGMENT_SHADER,
    GL_TEXTURE_2D,
    GL_TEXTURE0,
    GL_VERTEX_SHADER,
    glActiveTexture,
    glBindTexture,
    glBindVertexArray,
    glGetActiveUniform,
    glGetProgramiv,
    glGetString,
    glGetUniformLocation,
    glUniform1f,
    glUniform1i,
    glUniform2f,
    glUniform3f,
    glUniform4f,
    glUseProgram,
    GL_VERSION,
)
from OpenGL.GL import shaders  # type: ignore[import-untyped]

from .shader_compiler import wrap_shadertoy_shader
from .spec import ShaderSpec


def _detect_glsl_version() -> str:
    """Infer an appropriate GLSL version string from the current GL version.

    On macOS core profile with OpenGL 4.x we use ``410``.
    On modern desktop GL 3.3+ we use ``330 core``.
    Otherwise we fall back to ``120`` for broad compatibility.
    """
    try:
        version_bytes = glGetString(GL_VERSION)
        if not version_bytes:
            return "120"

        version_str = (
            version_bytes.decode() if isinstance(version_bytes, (bytes, bytearray)) else str(version_bytes)
        )
        import re

        match = re.match(r"(\d+)\.(\d+)", version_str)
        if not match:
            return "120"

        major = int(match.group(1))
        minor = int(match.group(2))

        if major > 4 or (major == 4 and minor >= 1):
            return "410"
        if major > 3 or (major == 3 and minor >= 3):
            return "330 core"
    except Exception:
        return "120"

    return "120"


class ShaderProgram:
    """Compiled OpenGL shader program with uniform/texture helpers."""

    def __init__(self, spec: ShaderSpec, fragment_source: str, glsl_version: Optional[str] = None) -> None:
        self.spec = spec
        self.fragment_source = fragment_source
        self.glsl_version = glsl_version
        self.program: Optional[int] = None
        self.uniform_locations: Dict[str, int] = {}

    @classmethod
    def from_file(cls, spec: ShaderSpec, shader_path: Path, glsl_version: Optional[str] = None) -> "ShaderProgram":
        with open(shader_path, "r") as f:
            fragment_source = f.read()
        return cls(spec, fragment_source, glsl_version)

    def compile(self, vao: Optional[int] = None) -> None:
        """Compile the shader program for the current GL context.

        A VAO can be optionally bound during compilation for core profiles that
        require one to be bound while linking attribute locations.
        """
        # Ensure we have a GLSL version; this requires an active context.
        if self.glsl_version is None:
            self.glsl_version = _detect_glsl_version()

        vertex_source, fragment_wrapped = wrap_shadertoy_shader(
            self.fragment_source,
            glsl_version=self.glsl_version,
            precision_statement="",
        )

        if vao is not None:
            glBindVertexArray(vao)

        try:
            vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
            self.program = shaders.compileProgram(vertex_shader, fragment_shader)
        except RuntimeError as e:
            # Make sure the VAO is unbound before propagating the error.
            if vao is not None:
                glBindVertexArray(0)
            raise RuntimeError(f"Shader compilation failed: {e}") from e

        if vao is not None:
            glBindVertexArray(0)

        # Cache uniform locations for fast updates.
        glUseProgram(self.program)
        self.uniform_locations.clear()

        num_uniforms = glGetProgramiv(self.program, GL_ACTIVE_UNIFORMS)
        for i in range(num_uniforms):
            name, size, uniform_type = glGetActiveUniform(self.program, i)
            if isinstance(name, (bytes, bytearray)):
                decoded = name.decode("utf-8")
            else:
                decoded = str(name)
            decoded = decoded.rstrip("\x00")
            if decoded.endswith("[0]"):
                decoded = decoded[:-3]

            loc = glGetUniformLocation(self.program, decoded)
            if loc >= 0:
                self.uniform_locations[decoded] = loc

        glUseProgram(0)

    def use(self) -> None:
        if self.program is None:
            raise RuntimeError("Shader program not compiled")
        glUseProgram(self.program)

    def set_uniform(self, name: str, value) -> None:
        if self.program is None:
            raise RuntimeError("Shader program not compiled")

        location = self.uniform_locations.get(name)
        if location is None:
            return

        if isinstance(value, (int, bool)):
            glUniform1i(location, int(value))
        elif isinstance(value, float):
            glUniform1f(location, float(value))
        elif isinstance(value, (list, tuple)):
            if len(value) == 2:
                glUniform2f(location, float(value[0]), float(value[1]))
            elif len(value) == 3:
                glUniform3f(location, float(value[0]), float(value[1]), float(value[2]))
            elif len(value) == 4:
                glUniform4f(
                    location,
                    float(value[0]),
                    float(value[1]),
                    float(value[2]),
                    float(value[3]),
                )
        else:
            raise ValueError(f"Unsupported uniform value type: {type(value)}")

    def set_texture(self, name: str, texture_unit: int, texture_id: Optional[int]) -> None:
        if self.program is None:
            raise RuntimeError("Shader program not compiled")
        if not texture_id or texture_id <= 0:
            return

        location = self.uniform_locations.get(name)
        if location is None:
            return

        glActiveTexture(GL_TEXTURE0 + texture_unit)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glUniform1i(location, texture_unit)