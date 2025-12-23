"""
Pyglet-based offscreen shader renderer.

This implementation uses pyglet for offscreen rendering, replacing GLUT on macOS.
Provides better multi-context support for multi-window applications.
"""
from OpenGL.GL import *  # type: ignore[import-untyped]
from .shader_renderer_base import ShaderRendererBase

class PygletShaderRenderer(ShaderRendererBase):
    """\n    Pyglet-based offscreen shader renderer.\n\n    Features:\n    - Offscreen rendering via hidden pyglet window\n    - Native multi-context support\n    - Works with pyglet-based windowing\n    - Compatible with OpenGL 2.1 (macOS)\n    """

    def __init__(self, width: int, height: int):
        """
        Initialize pyglet shader renderer.

        Args:
            width: Render width in pixels
            height: Render height in pixels
        """
        self.pyglet_window = None
        super().__init__(width, height, scale=1)
        print(f'Pyglet shader renderer initialized: {width}×{height} (offscreen)')

    def make_context_current(self) -> bool:
        """Make this pyglet window's context current."""
        if not self.pyglet_window:
            return False
        try:
            self.pyglet_window.switch_to()
            return True
        except Exception as e:
            print(f'Error making pyglet context current: {e}')
            return False

    def _init_context(self):
        """Initialize pyglet offscreen context with OpenGL 2.1 compatibility."""
        try:
            import pyglet
            from pyglet import gl
        except ImportError:
            raise ImportError(
                "pyglet is required for PygletShaderRenderer. Install with: pip install pyglet"
            ) from None

        print("Creating config")
        config = gl.Config(double_buffer=True, depth_size=24, major_version=2, minor_version=1)
        print(f"Config created: {config}")
        print(f"Config double_buffer: {config.double_buffer}")
        print(f"Config depth_size: {config.depth_size}")
        print(f"Config major_version: {config.major_version}")
        print(f"Config minor_version: {config.minor_version}")
        print("Creating window")
        self.pyglet_window = pyglet.window.Window(
            width=self.width,
            height=self.height,
            caption="Shader Renderer (Offscreen)",
            visible=False,
            config=config,
        )
        print("Switching to window")
        self.pyglet_window.switch_to()
        print("Querying OpenGL version")
        gl_version = glGetString(GL_VERSION)
        glsl_version = glGetString(GL_SHADING_LANGUAGE_VERSION)
        print("Created offscreen OpenGL context via Pyglet")
        print(f"OpenGL Version: {(gl_version.decode() if gl_version else 'Unknown')}")
        print(f"GLSL Version: {(glsl_version.decode() if glsl_version else 'Unknown')}")

    def _get_viewport_width(self) -> int:
        """Get viewport width."""
        return self.width

    def _get_viewport_height(self) -> int:
        """Get viewport height."""
        return self.height

    def _swap_buffers(self):
        """Swap buffers (no-op for offscreen rendering)."""
        return

    def _get_glsl_version(self) -> str:
        """Use desktop OpenGL GLSL version 120 for macOS compatibility."""
        return '120'

    def _get_attribute_keyword(self) -> str:
        """Use 'attribute' keyword for GLSL 120."""
        return 'attribute'

    def _get_precision_statement(self) -> str:
        """Desktop GLSL doesn't require precision qualifiers."""
        return ''

    def cleanup(self):
        """Clean up pyglet resources."""
        self.uniform_manager.cleanup()
        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()
        if self.pyglet_window:
            try:
                self.pyglet_window.close()
            except Exception:
                pass
        print('Pyglet context cleaned up')