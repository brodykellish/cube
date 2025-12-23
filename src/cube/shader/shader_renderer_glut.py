"""
GLUT-based offscreen shader renderer.

This implementation uses GLUT for offscreen rendering when pygame
is already in use. This avoids conflicts from creating multiple
pygame displays.
"""
from OpenGL.GL import *  # type: ignore[import-untyped]
from .shader_renderer_base import ShaderRendererBase

class GLUTShaderRenderer(ShaderRendererBase):
    """\n    GLUT-based offscreen shader renderer.\n    \n    Features:\n    - Offscreen rendering via hidden GLUT window\n    - No pygame dependency conflicts\n    - Works on MacOS when pygame already has a display\n    """

    def __init__(self, width: int, height: int):
        """
        Initialize GLUT shader renderer.

        Args:
            width: Render width in pixels
            height: Render height in pixels
        """
        self.glut_window = None
        super().__init__(width, height, scale=1)
        print(f'GLUT shader renderer initialized: {width}×{height} (offscreen)')

    def make_context_current(self) -> bool:
        """Make this GLUT window's context current."""
        if not self.glut_window:
            return False
        try:
            from OpenGL.GLUT import glutSetWindow
            glutSetWindow(self.glut_window)
            return True
        except Exception as e:
            print(f'Error making GLUT context current: {e}')
            return False

    def _init_context(self):
        """Initialize GLUT offscreen context with OpenGL 3.3 Core Profile."""
        from OpenGL.GLUT import glutInit, glutInitDisplayMode, glutInitWindowSize, glutCreateWindow, glutHideWindow, glutDisplayFunc, GLUT_RGBA, GLUT_DOUBLE, GLUT_DEPTH
        try:
            glutInit()
        except Exception:
            # If GLUT is already initialised or fails, we still try to create a window.
            pass

        try:
            from OpenGL.GLUT import glutInitContextVersion, glutInitContextProfile, GLUT_CORE_PROFILE
            from OpenGL.error import NullFunctionError

            if glutInitContextVersion and glutInitContextProfile:
                glutInitContextVersion(3, 3)
                glutInitContextProfile(GLUT_CORE_PROFILE)
                print('Requested OpenGL 3.3 Core Profile')
            else:
                raise NullFunctionError('Context version functions not available')
        except (ImportError, AttributeError, Exception):
            print('Warning: GLUT context version/profile not available on this platform')
            print('Falling back to default OpenGL context (macOS will use highest available)')

        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
        glutInitWindowSize(self.width, self.height)
        self.glut_window = glutCreateWindow(b'Shader Renderer')

        def dummy_display():
            return

        glutDisplayFunc(dummy_display)
        glutHideWindow()
        from OpenGL.GL import glGetString, GL_VERSION, GL_SHADING_LANGUAGE_VERSION

        gl_version = glGetString(GL_VERSION)
        glsl_version = glGetString(GL_SHADING_LANGUAGE_VERSION)
        print('Created offscreen OpenGL context via GLUT')
        print(f"OpenGL Version: {(gl_version.decode() if gl_version else 'Unknown')}")
        print(f"GLSL Version: {(glsl_version.decode() if glsl_version else 'Unknown')}")

    def _get_viewport_width(self) -> int:
        """Get viewport width."""  # inserted
        return self.width

    def _get_viewport_height(self) -> int:
        """Get viewport height."""  # inserted
        return self.height

    def _swap_buffers(self):
        """Swap buffers (no-op for offscreen rendering)."""  # inserted
        return

    def _get_glsl_version(self) -> str:
        """Use desktop OpenGL GLSL version 120 for macOS compatibility."""  # inserted
        return '120'

    def _get_attribute_keyword(self) -> str:
        """Use \'attribute\' keyword for GLSL 120."""  # inserted
        return 'attribute'

    def _get_precision_statement(self) -> str:
        """Desktop GLSL doesn\'t require precision qualifiers."""  # inserted
        return ''

    def cleanup(self):
        """Clean up GLUT resources."""  # inserted
        self.uniform_manager.cleanup()
        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()
        print('GLUT context cleaned up')