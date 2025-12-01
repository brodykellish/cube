"""
Mixer Channel - holds shader state and renderer for a single channel.
"""

from typing import Optional
from pathlib import Path


class MixerChannel:
    """
    Single mixer channel.

    Holds shader path and renderer instance. Each channel owns its shader
    lifecycle (loading, rendering, cleanup).
    """

    def __init__(self, channel_id: str):
        """
        Initialize mixer channel.

        Args:
            channel_id: Channel identifier ('A' or 'B')
        """
        self.channel_id = channel_id
        self.shader_path: Optional[str] = None
        self.shader_renderer = None  # Will be ShaderRenderer when loaded

    def load_shader(self, shader_path: str, width: int, height: int, camera_mode: str = 'spherical'):
        """
        Load a shader into this channel.

        Args:
            shader_path: Path to shader file
            width: Render width
            height: Render height
            camera_mode: Camera mode ('spherical' or 'static')
        """
        from cube.shader import ShaderRenderer, SphericalCamera, StaticCamera

        # Clean up old renderer
        if self.shader_renderer is not None:
            try:
                self.shader_renderer.cleanup()
            except Exception as e:
                print(f"Warning: Error cleaning up shader renderer on channel {self.channel_id}: {e}")

        # Create new renderer
        self.shader_renderer = ShaderRenderer(width, height)

        # Set camera mode
        if camera_mode == 'spherical':
            self.shader_renderer.set_camera_mode(SphericalCamera())
        else:
            self.shader_renderer.set_camera_mode(StaticCamera())

        # Load shader
        self.shader_renderer.load_shader(shader_path)
        self.shader_path = shader_path

        print(f"Channel {self.channel_id}: Loaded shader {Path(shader_path).name}")

    def has_shader(self) -> bool:
        """Check if channel has a shader loaded."""
        return self.shader_renderer is not None

    def render(self):
        """Render this channel's shader (if loaded)."""
        if self.shader_renderer is not None:
            # Activate this renderer's OpenGL context if it's a GLUT renderer
            self._activate_context()
            self.shader_renderer.render()

    def _activate_context(self):
        """Activate this channel's OpenGL context (for GLUT multi-context support)."""
        # Check if this is a GLUT renderer with a window
        if hasattr(self.shader_renderer, 'glut_window') and self.shader_renderer.glut_window is not None:
            try:
                from OpenGL.GLUT import glutSetWindow
                glutSetWindow(self.shader_renderer.glut_window)
            except Exception as e:
                # If context switching fails, continue anyway (may work)
                pass

    def read_pixels(self):
        """Read rendered pixels from this channel."""
        if self.shader_renderer is not None:
            # Activate this renderer's OpenGL context if it's a GLUT renderer
            self._activate_context()
            return self.shader_renderer.read_pixels()
        return None

    def cleanup(self):
        """Clean up shader renderer."""
        if self.shader_renderer is not None:
            try:
                self.shader_renderer.cleanup()
            except Exception as e:
                print(f"Warning: Error cleaning up channel {self.channel_id}: {e}")
            self.shader_renderer = None
            self.shader_path = None
