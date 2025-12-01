"""
EGL-based shader renderer for Raspberry Pi LED matrix.

This implementation uses EGL for offscreen rendering on Raspberry Pi.
The rendered framebuffer is intended to be pulled and mixed with other
layers by the display utility.
"""

from OpenGL.GL import *
from OpenGL import EGL
from ctypes import pointer, c_int

from .shader_renderer_base import ShaderRendererBase


class EGLShaderRenderer(ShaderRendererBase):
    """
    EGL-based shader renderer for Raspberry Pi.
    
    Features:
    - Offscreen EGL rendering (no X11 required)
    - Headless operation for LED matrix driving
    - RGB framebuffer extraction for layer mixing
    """
    
    def __init__(self, width: int, height: int):
        """
        Initialize EGL shader renderer.
        
        Args:
            width: Render width in pixels
            height: Render height in pixels
        """
        self.egl_display = None
        self.egl_context = None
        self.egl_surface = None
        
        super().__init__(width, height, scale=1)
        print(f"EGL shader renderer initialized: {width}×{height} (headless)")
    
    def _init_context(self):
        """Initialize EGL context for offscreen rendering."""
        self.egl_display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
        if self.egl_display == EGL.EGL_NO_DISPLAY:
            raise RuntimeError("Failed to get EGL display")
        
        major = c_int()
        minor = c_int()
        if not EGL.eglInitialize(self.egl_display, pointer(major), pointer(minor)):
            raise RuntimeError("Failed to initialize EGL")
        
        print(f"EGL initialized: version {major.value}.{minor.value}")
        
        config_attribs = [
            EGL.EGL_SURFACE_TYPE, EGL.EGL_PBUFFER_BIT,
            EGL.EGL_RENDERABLE_TYPE, EGL.EGL_OPENGL_BIT,
            EGL.EGL_RED_SIZE, 8,
            EGL.EGL_GREEN_SIZE, 8,
            EGL.EGL_BLUE_SIZE, 8,
            EGL.EGL_ALPHA_SIZE, 8,
            EGL.EGL_DEPTH_SIZE, 24,
            EGL.EGL_NONE
        ]
        
        configs = (EGL.EGLConfig * 1)()
        num_configs = c_int()
        
        if not EGL.eglChooseConfig(
            self.egl_display,
            (c_int * len(config_attribs))(*config_attribs),
            configs,
            1,
            pointer(num_configs)
        ) or num_configs.value == 0:
            raise RuntimeError("Failed to choose EGL config")
        
        if not EGL.eglBindAPI(EGL.EGL_OPENGL_API):
            raise RuntimeError("Failed to bind OpenGL API")
        
        pbuffer_attribs = [
            EGL.EGL_WIDTH, self.width,
            EGL.EGL_HEIGHT, self.height,
            EGL.EGL_NONE
        ]
        
        self.egl_surface = EGL.eglCreatePbufferSurface(
            self.egl_display,
            configs[0],
            (c_int * len(pbuffer_attribs))(*pbuffer_attribs)
        )
        
        if self.egl_surface == EGL.EGL_NO_SURFACE:
            raise RuntimeError("Failed to create EGL pbuffer surface")
        
        context_attribs = [
            EGL.EGL_CONTEXT_MAJOR_VERSION, 2,
            EGL.EGL_CONTEXT_MINOR_VERSION, 1,
            EGL.EGL_NONE
        ]
        
        self.egl_context = EGL.eglCreateContext(
            self.egl_display,
            configs[0],
            EGL.EGL_NO_CONTEXT,
            (c_int * len(context_attribs))(*context_attribs)
        )
        
        if self.egl_context == EGL.EGL_NO_CONTEXT:
            raise RuntimeError("Failed to create EGL context")
        
        if not EGL.eglMakeCurrent(
            self.egl_display,
            self.egl_surface,
            self.egl_surface,
            self.egl_context
        ):
            raise RuntimeError("Failed to make EGL context current")
        
        print("Created offscreen OpenGL context via EGL (headless)")
    
    def _get_viewport_width(self) -> int:
        """Get viewport width."""
        return self.width
    
    def _get_viewport_height(self) -> int:
        """Get viewport height."""
        return self.height
    
    def _swap_buffers(self):
        """Swap buffers (no-op for offscreen rendering)."""
        pass
    
    def cleanup(self):
        """Clean up EGL resources."""
        self.input_manager.cleanup()
        
        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()
        
        if self.egl_display is not None:
            try:
                if self.egl_context is not None:
                    EGL.eglDestroyContext(self.egl_display, self.egl_context)
                if self.egl_surface is not None:
                    EGL.eglDestroySurface(self.egl_display, self.egl_surface)
                EGL.eglTerminate(self.egl_display)
                
                print("EGL context cleaned up")
            except Exception as e:
                print(f"Warning: Error cleaning up EGL: {e}")

