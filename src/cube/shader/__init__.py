"""
Shader rendering module for HUB75 LED matrices.

Platform-aware shader renderer with uniform source abstraction for clean separation of concerns.

Components:
- ShaderRenderer: Platform-aware shader renderer factory
  - MacOS: GLUTShaderRenderer (offscreen, for development)
  - Linux/Raspberry Pi: EGLShaderRenderer (headless, for LED matrix)
- UniformSourceManager: Coordinates multiple uniform sources
- Uniform sources: MouseUniformSource, CameraUniformSource, AudioUniformMappingSource, VideoUniformSource
- Camera modes: SphericalCamera, StaticCamera

Example usage:
    >>> from cube.shader import (
    ...     ShaderRenderer, SphericalCamera
    ... )
    >>> # Create offscreen renderer (use with cube_control.py or similar)
    >>> renderer = ShaderRenderer(64, 64)
    >>> renderer.set_camera_mode(SphericalCamera())
    >>> renderer.load_shader("my_shader.glsl")
    >>> renderer.render()
    >>> pixels = renderer.read_pixels()
"""
from .shader_renderer import ShaderRenderer, create_shader_renderer
from .uniform_sources import UniformSource, UniformSourceManager, MouseUniformSource
from .camera_modes import CameraMode, SphericalCamera, StaticCamera
from .camera_uniform_source import CameraUniformSource

InputSource = UniformSource
InputManager = UniformSourceManager

__all__ = [
    "ShaderRenderer",
    "create_shader_renderer",
    "InputSource",
    "UniformSource",
    "UniformSourceManager",
    "MouseUniformSource",
    "InputManager",
    "CameraUniformSource",
    "CameraMode",
    "SphericalCamera",
    "StaticCamera",
]

