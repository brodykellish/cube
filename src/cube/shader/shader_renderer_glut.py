"""
GLUT-based offscreen shader renderer.

This implementation uses GLUT for offscreen rendering when pygame
is already in use. This avoids conflicts from creating multiple pygame displays.
"""

from OpenGL.GL import *

from .shader_renderer_base import ShaderRendererBase


class GLUTShaderRenderer(ShaderRendererBase):
    """
    GLUT-based offscreen shader renderer.
    
    Features:
    - Offscreen rendering via hidden GLUT window
    - No pygame dependency conflicts
    - Works on MacOS when pygame already has a display
    """
    
    def __init__(self, width: int, height: int):
        """
        Initialize GLUT shader renderer.
        
        Args:
            width: Render width in pixels
            height: Render height in pixels
        """
        self.glut_window = None
        super().__init__(width, height, scale=1)
        print(f"GLUT shader renderer initialized: {width}×{height} (offscreen)")
    
    def make_context_current(self) -> bool:
        """Make this GLUT window's context current."""
        if not self.glut_window:
            return False

        try:
            from OpenGL.GLUT import glutSetWindow
            glutSetWindow(self.glut_window)
            return True
        except Exception as e:
            print(f"Error making GLUT context current: {e}")
            return False

    def _init_context(self):
        """Initialize GLUT offscreen context."""
        from OpenGL.GLUT import (
            glutInit, glutInitDisplayMode, glutInitWindowSize,
            glutCreateWindow, glutHideWindow, glutDisplayFunc,
            GLUT_RGBA, GLUT_DOUBLE, GLUT_DEPTH
        )
        
        try:
            glutInit()
        except Exception as e:
            print(f"GLUT already initialized (this is OK)")

        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
        glutInitWindowSize(self.width, self.height)
        self.glut_window = glutCreateWindow(b"Shader Renderer")
        
        def dummy_display():
            pass
        glutDisplayFunc(dummy_display)
        
        glutHideWindow()
        
        print("Created offscreen OpenGL context via GLUT")
    
    def _get_viewport_width(self) -> int:
        """Get viewport width."""
        return self.width
    
    def _get_viewport_height(self) -> int:
        """Get viewport height."""
        return self.height
    
    def _swap_buffers(self):
        """Swap buffers (no-op for offscreen rendering)."""
        pass

    def _get_glsl_version(self) -> str:
        """Use desktop OpenGL GLSL version 120 for macOS."""
        return "120"

    def _get_attribute_keyword(self) -> str:
        """Use 'attribute' keyword for GLSL 120."""
        return "attribute"

    def _get_precision_statement(self) -> str:
        """Desktop GLSL doesn't require precision qualifiers."""
        return ""

    def cleanup(self):
        """Clean up GLUT resources."""
        self.uniform_manager.cleanup()

        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()

        print("GLUT context cleaned up")

