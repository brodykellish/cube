"""
Pyglet-based offscreen shader renderer using FBO.

Uses framebuffer objects for offscreen rendering instead of hidden windows.
More efficient and avoids multi-window issues.
"""
from OpenGL.GL import *  # type: ignore[import-untyped]
from .shader_renderer_base import ShaderRendererBase

class PygletShaderRendererFBO(ShaderRendererBase):
    """\n    Pyglet-based offscreen shader renderer using FBO.\n\n    Uses a shared pyglet context and framebuffer objects for offscreen rendering.\n    """
    _shared_window = None
    _window_refcount = 0

    def __init__(self, width: int, height: int):
        """
        Initialize pyglet FBO shader renderer.

        Args:
            width: Render width in pixels
            height: Render height in pixels
        """
        self.fbo = None
        self.color_texture = None
        self.depth_buffer = None
        print(f'Initializing Pyglet FBO shader renderer: {width}×{height}')
        super().__init__(width, height, scale=1)
        print(f'Pyglet FBO shader renderer initialized: {width}×{height} (offscreen)')

    def make_context_current(self) -> bool:
        """Make the shared pyglet context current."""
        if not PygletShaderRendererFBO._shared_window:
            return False
        try:
            PygletShaderRendererFBO._shared_window.switch_to()
            if self.fbo:
                glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
            return True
        except Exception as e:
            print(f'Error making pyglet FBO context current: {e}')
            return False

    def _init_context(self):
        """Initialize shared pyglet context and create FBO."""
        try:
            import pyglet
            from pyglet import gl
        except ImportError:
            raise ImportError(
                "pyglet is required for PygletShaderRendererFBO. Install with: pip install pyglet"
            ) from None

        if PygletShaderRendererFBO._shared_window is None:
            print("Creating shared pyglet context for shader rendering...")
            PygletShaderRendererFBO._shared_window = pyglet.window.Window(
                width=64,
                height=64,
                caption="Shader Context (Shared)",
                visible=False,
            )
            PygletShaderRendererFBO._shared_window.switch_to()
            gl_version = glGetString(GL_VERSION)
            glsl_version = glGetString(GL_SHADING_LANGUAGE_VERSION)
            print("Created shared OpenGL context via Pyglet")
            print(f"OpenGL Version: {(gl_version.decode() if gl_version else 'Unknown')}")
            print(f"GLSL Version: {(glsl_version.decode() if glsl_version else 'Unknown')}")

        PygletShaderRendererFBO._window_refcount += 1
        PygletShaderRendererFBO._shared_window.switch_to()
        self._create_fbo()

    def _create_fbo(self):
        """Create framebuffer object for offscreen rendering."""
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        self.color_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.color_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.width, self.height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.color_texture, 0)
        self.depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_buffer)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, self.width, self.height)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth_buffer)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status!= GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f'Framebuffer incomplete: {status}')
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def _get_viewport_width(self) -> int:
        """Get viewport width."""
        return self.width

    def _get_viewport_height(self) -> int:
        """Get viewport height."""
        return self.height

    def _swap_buffers(self):
        """Swap buffers (no-op for FBO rendering)."""
        return

    def _get_glsl_version(self) -> str:
        """
        Get GLSL version based on OpenGL version.

        macOS with OpenGL 4.x uses core profile (GLSL 410).
        Linux/Windows typically use compatibility profile (GLSL 120).
        Raspberry Pi uses OpenGL ES (handled by EGL renderer).
        """
        gl_version_str = glGetString(GL_VERSION)
        if gl_version_str:
            version_str = gl_version_str.decode()
            import re
            match = re.match('(\\d+)\\.(\\d+)', version_str)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                if major > 4 or (major == 4 and minor >= 1):
                    return '410'
        return '120'

    def _get_attribute_keyword(self) -> str:
        """Get attribute keyword based on GLSL version."""
        version = self._get_glsl_version()
        return 'in' if version != '120' else 'attribute'

    def _get_precision_statement(self) -> str:
        """Desktop GLSL doesn't require precision qualifiers."""
        return ''

    def cleanup(self):
        """Clean up FBO resources."""
        self.uniform_manager.cleanup()
        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()
        if hasattr(self, 'vao') and self.vao:
            glDeleteVertexArrays(1, [self.vao])
        if hasattr(self, 'vbo') and self.vbo:
            glDeleteBuffers(1, [self.vbo])
        if self.fbo:
            glDeleteFramebuffers(1, [self.fbo])
        if self.color_texture:
            glDeleteTextures([self.color_texture])
        if self.depth_buffer:
            glDeleteRenderbuffers(1, [self.depth_buffer])
        PygletShaderRendererFBO._window_refcount -= 1
        if PygletShaderRendererFBO._window_refcount == 0 and PygletShaderRendererFBO._shared_window:
            try:
                PygletShaderRendererFBO._shared_window.close()
            except:
                pass
            PygletShaderRendererFBO._shared_window = None
        print('Pyglet FBO context cleaned up')