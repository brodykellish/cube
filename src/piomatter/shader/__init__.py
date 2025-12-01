"""
Shader rendering module for HUB75 LED matrices.

Platform-aware shader renderer with input abstraction for clean separation of concerns.

Components:
- ShaderRenderer: Platform-aware shader renderer factory
  - MacOS: GLUTShaderRenderer (offscreen, for development)
  - Linux/Raspberry Pi: EGLShaderRenderer (headless, for LED matrix)
- InputManager: Coordinates multiple input sources
- Input sources: KeyboardInput, AudioFileInput, MicrophoneInput, CameraInput
- Camera modes: SphericalCamera, StaticCamera
- AudioProcessor: Audio analysis and beat detection

Example usage:
    >>> from piomatter.shader import (
    ...     ShaderRenderer, AudioFileInput, SphericalCamera
    ... )
    >>> # Create offscreen renderer (use with cube_control.py or similar)
    >>> renderer = ShaderRenderer(64, 64)
    >>> renderer.set_camera_mode(SphericalCamera())
    >>> renderer.add_input_source(AudioFileInput("music.mp3"))
    >>> renderer.load_shader("my_shader.glsl")
    >>> renderer.render()
    >>> pixels = renderer.read_pixels()
"""

from .shader_renderer import ShaderRenderer, create_shader_renderer
from .input_sources import (
    InputSource, InputManager,
    KeyboardInput, AudioFileInput, MicrophoneInput, CameraInput
)
from .camera_modes import CameraMode, SphericalCamera, StaticCamera
from .audio_processor import AudioProcessor

__all__ = [
    # Renderer
    'ShaderRenderer',
    'create_shader_renderer',

    # Input abstraction
    'InputSource',
    'InputManager',
    'KeyboardInput',
    'AudioFileInput',
    'MicrophoneInput',
    'CameraInput',

    # Camera modes
    'CameraMode',
    'SphericalCamera',
    'StaticCamera',

    # Audio processing
    'AudioProcessor',
]
