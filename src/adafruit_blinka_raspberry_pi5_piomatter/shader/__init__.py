"""
Shader rendering module for HUB75 LED matrices.

Unified shader renderer with input abstraction for clean separation of concerns.

Components:
- ShaderRenderer: Standalone shader renderer with InputManager integration
- InputManager: Coordinates multiple input sources
- Input sources: KeyboardInput, AudioFileInput, MicrophoneInput, CameraInput
- Camera modes: SphericalCamera, StaticCamera
- AudioProcessor: Audio analysis and beat detection

Example usage:
    >>> from adafruit_blinka_raspberry_pi5_piomatter.shader import (
    ...     ShaderRenderer, AudioFileInput, SphericalCamera
    ... )
    >>> renderer = ShaderRenderer(64, 64, windowed=True)
    >>> renderer.set_camera_mode(SphericalCamera())
    >>> renderer.add_input_source(AudioFileInput("music.mp3"))
    >>> renderer.load_shader("my_shader.glsl")
    >>> while running:
    ...     renderer.render()
    ...     running = renderer.handle_events()
"""

from .shader_renderer import ShaderRenderer
from .input_sources import (
    InputSource, InputManager,
    KeyboardInput, AudioFileInput, MicrophoneInput, CameraInput
)
from .camera_modes import CameraMode, SphericalCamera, StaticCamera
from .audio_processor import AudioProcessor

__all__ = [
    # Renderer
    'ShaderRenderer',

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
