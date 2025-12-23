"""
EGL-based shader renderer for Raspberry Pi LED matrix.

This implementation uses EGL for offscreen rendering on Raspberry Pi.
The rendered framebuffer is intended to be pulled and mixed with other
layers by the display utility.
"""
import os
from ctypes import CDLL, c_int, c_void_p, pointer

os.environ['PYOPENGL_PLATFORM'] = 'egl'

from OpenGL.GL import *  # type: ignore[import-untyped]
from OpenGL import EGL  # type: ignore[import-untyped]
from OpenGL.platform import PLATFORM  # type: ignore[import-untyped]

from .shader_renderer_base import ShaderRendererBase

class EGLShaderRenderer(ShaderRendererBase):
    """\n    EGL-based shader renderer for Raspberry Pi.\n    \n    Features:\n    - Offscreen EGL rendering (no X11 required)\n    - Headless operation for LED matrix driving\n    - RGB framebuffer extraction for layer mixing\n    """

    def __init__(self, width: int, height: int):
        """\n        Initialize EGL shader renderer.\n\n        Args:\n            width: Render width in pixels\n            height: Render height in pixels\n        """  # inserted
        self.egl_display = None
        self.egl_context = None
        self.egl_surface = None
        self.drm_fd = None
        self.gbm_device = None
        self.fbo = None
        self.fbo_texture = None
        super().__init__(width, height, scale=1)
        print(f'EGL shader renderer initialized: {width}×{height} (headless)')

    def make_context_current(self) -> bool:
        """Make this EGL context current."""  # inserted
        if not self.egl_display or not self.egl_context or (not self.egl_surface):
            return False
        try:
            result = EGL.eglMakeCurrent(self.egl_display, self.egl_surface, self.egl_surface, self.egl_context)
            return bool(result)
        except Exception as e:
            print(f'Error making EGL context current: {e}')
            return False

    def _init_context(self):
        """Initialize EGL context for offscreen rendering using GBM."""  # inserted
        # Step 1: try to create a GBM device and EGL display bound to /dev/dri/card0.
        try:
            gbm = CDLL('libgbm.so.1')
            drm_card = '/dev/dri/card0'
            if not os.path.exists(drm_card):
                raise RuntimeError(f'DRM device {drm_card} not found')
            self.drm_fd = os.open(drm_card, os.O_RDWR)
            gbm.gbm_create_device.argtypes = [c_int]
            gbm.gbm_create_device.restype = c_void_p
            self.gbm_device = gbm.gbm_create_device(self.drm_fd)
            if not self.gbm_device:
                raise RuntimeError('Failed to create GBM device')

            EGL_PLATFORM_GBM_KHR = 0x31D7  # 12759

            egl_get_platform_display = EGL.eglGetProcAddress(b'eglGetPlatformDisplayEXT')
            if egl_get_platform_display:
                self.egl_display = egl_get_platform_display(EGL_PLATFORM_GBM_KHR, c_void_p(self.gbm_device), None)
            else:
                self.egl_display = EGL.eglGetDisplay(c_void_p(self.gbm_device))

            if self.egl_display == EGL.EGL_NO_DISPLAY:
                raise RuntimeError('Failed to get EGL display from GBM')
            print('Using GBM device for EGL display')
        except Exception as e:
            # Fall back to default display if GBM path fails.
            print(f'Warning: Could not use GBM ({e}), falling back to EGL_DEFAULT_DISPLAY')
            self.egl_display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
            if self.egl_display == EGL.EGL_NO_DISPLAY:
                raise RuntimeError('Failed to get EGL display')

        # Step 2: initialise EGL and create a context/surface.
        major = c_int()
        minor = c_int()
        if not EGL.eglInitialize(self.egl_display, pointer(major), pointer(minor)):
            error = EGL.eglGetError()
            raise RuntimeError(f'Failed to initialize EGL (error: 0x{error:x})')
        print(f'EGL initialized: version {major.value}.{minor.value}')

        if not EGL.eglBindAPI(EGL.EGL_OPENGL_ES_API):
            error = EGL.eglGetError()
            raise RuntimeError(f'Failed to bind OpenGL ES API (error: 0x{error:x})')

        config_attribs = [
            EGL.EGL_RENDERABLE_TYPE,
            EGL.EGL_OPENGL_ES2_BIT,
            EGL.EGL_SURFACE_TYPE,
            EGL.EGL_PBUFFER_BIT,
            EGL.EGL_NONE,
        ]
        configs = (EGL.EGLConfig * 10)()
        num_configs = c_int()
        if not EGL.eglChooseConfig(
            self.egl_display,
            (c_int * len(config_attribs))(*config_attribs),
            configs,
            10,
            pointer(num_configs),
        ):
            error = EGL.eglGetError()
            raise RuntimeError(f'eglChooseConfig failed (error: 0x{error:x})')

        if num_configs.value == 0:
            print('Warning: No configs found with PBuffer, trying any config...')
            config_attribs = [
                EGL.EGL_RENDERABLE_TYPE,
                EGL.EGL_OPENGL_ES2_BIT,
                EGL.EGL_NONE,
            ]
            if not EGL.eglChooseConfig(
                self.egl_display,
                (c_int * len(config_attribs))(*config_attribs),
                configs,
                10,
                pointer(num_configs),
            ):
                error = EGL.eglGetError()
                raise RuntimeError(f'eglChooseConfig failed on retry (error: 0x{error:x})')
            if num_configs.value == 0:
                raise RuntimeError('Failed to find any compatible EGL config')

        print(f'Found {num_configs.value} compatible EGL config(s)')

        extensions = EGL.eglQueryString(self.egl_display, EGL.EGL_EXTENSIONS)
        supports_surfaceless = extensions and b'EGL_KHR_surfaceless_context' in extensions

        self.egl_surface = EGL.EGL_NO_SURFACE
        if not supports_surfaceless:
            pbuffer_attribs = [
                EGL.EGL_WIDTH,
                self.width,
                EGL.EGL_HEIGHT,
                self.height,
                EGL.EGL_NONE,
            ]
            self.egl_surface = EGL.eglCreatePbufferSurface(
                self.egl_display,
                configs[0],
                (c_int * len(pbuffer_attribs))(*pbuffer_attribs),
            )
            if self.egl_surface == EGL.EGL_NO_SURFACE:
                error = EGL.eglGetError()
                raise RuntimeError(f'Failed to create EGL pbuffer surface (error: 0x{error:x})')
            print('Created PBuffer surface for offscreen rendering')
        else:
            print('Using surfaceless context for offscreen rendering')

        context_attribs = [EGL.EGL_CONTEXT_CLIENT_VERSION, 2, EGL.EGL_NONE]
        self.egl_context = EGL.eglCreateContext(
            self.egl_display,
            configs[0],
            EGL.EGL_NO_CONTEXT,
            (c_int * len(context_attribs))(*context_attribs),
        )
        if self.egl_context == EGL.EGL_NO_CONTEXT:
            error = EGL.eglGetError()
            raise RuntimeError(f'Failed to create EGL context (error: 0x{error:x})')

        if not EGL.eglMakeCurrent(self.egl_display, self.egl_surface, self.egl_surface, self.egl_context):
            error = EGL.eglGetError()
            raise RuntimeError(f'Failed to make EGL context current (error: 0x{error:x})')

        print('Created offscreen OpenGL context via EGL (headless)')

        try:
            PLATFORM.CurrentContextIsValid = lambda: True
            PLATFORM.GetCurrentContext = lambda: self.egl_context
        except Exception as e:
            print(f'Warning: Could not register EGL context with PyOpenGL platform: {e}')

        self._create_fbo()

    def _create_fbo(self):
        """Create framebuffer object for offscreen rendering."""  # inserted
        fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status!= GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f'Framebuffer is not complete: 0x{status:x}')
        self.fbo = fbo
        self.fbo_texture = texture
        print(f'Created FBO {fbo} with texture {texture} ({self.width}x{self.height})')

    def _get_viewport_width(self) -> int:
        """Get viewport width."""  # inserted
        return self.width

    def _get_viewport_height(self) -> int:
        """Get viewport height."""  # inserted
        return self.height

    def _swap_buffers(self):
        """Swap buffers (no-op for offscreen rendering)."""  # inserted
        glFlush()

    def render(self):
        """Render a frame, ensuring EGL context is current."""  # inserted
        if not EGL.eglMakeCurrent(self.egl_display, self.egl_surface, self.egl_surface, self.egl_context):
            error = EGL.eglGetError()
            raise RuntimeError(f'Failed to make context current for render (error: 0x{error:x})')
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        super().render()

    def read_pixels(self):
        """Read pixels from FBO, ensuring proper binding."""  # inserted
        import numpy as np
        if not EGL.eglMakeCurrent(self.egl_display, self.egl_surface, self.egl_surface, self.egl_context):
            error = EGL.eglGetError()
            raise RuntimeError(f'Failed to make context current for read_pixels (error: 0x{error:x})')
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        pixel_data = glReadPixels(0, 0, self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE)
        pixels = np.frombuffer(pixel_data, dtype=np.uint8).reshape(self.height, self.width, 4)
        pixels = np.flipud(pixels)
        return pixels[:, :, :3].copy()

    def cleanup(self):
        """Clean up EGL and OpenGL resources."""
        # Clean up uniform sources first.
        self.uniform_manager.cleanup()

        # Ensure the EGL context is current before deleting GL resources.
        if self.egl_display is not None and self.egl_context is not None:
            try:
                surface = self.egl_surface if self.egl_surface is not None else EGL.EGL_NO_SURFACE
                EGL.eglMakeCurrent(self.egl_display, surface, surface, self.egl_context)
            except Exception as e:
                print(f'Warning: Failed to make EGL context current during cleanup: {e}')

        # Finish any pending GL work.
        try:
            glFinish()
        except Exception:
            pass

        # Delete GL program.
        if self.program is not None:
            try:
                glDeleteProgram(self.program)
            except Exception:
                pass
            finally:
                self.program = None

        # Delete VBO.
        if self.vbo is not None:
            try:
                glDeleteBuffers(1, [self.vbo])
            except Exception:
                pass
            finally:
                self.vbo = None

        # Delete any textures created for channels.
        for tex_id in self.textures.values():
            if tex_id is not None:
                try:
                    glDeleteTextures([tex_id])
                except Exception:
                    pass
        self.textures.clear()

        # Delete FBO and its texture.
        if self.fbo is not None:
            try:
                glBindFramebuffer(GL_FRAMEBUFFER, 0)
                glDeleteFramebuffers(1, [self.fbo])
            except Exception:
                pass
            finally:
                self.fbo = None

        if self.fbo_texture is not None:
            try:
                glDeleteTextures([self.fbo_texture])
            except Exception:
                pass
            finally:
                self.fbo_texture = None

        # Tear down EGL objects.
        if self.egl_display is not None:
            try:
                EGL.eglMakeCurrent(self.egl_display, EGL.EGL_NO_SURFACE, EGL.EGL_NO_SURFACE, EGL.EGL_NO_CONTEXT)

                if self.egl_context is not None:
                    EGL.eglDestroyContext(self.egl_display, self.egl_context)
                    self.egl_context = None

                    if self.egl_surface is not None and self.egl_surface != EGL.EGL_NO_SURFACE:
                        EGL.eglDestroySurface(self.egl_display, self.egl_surface)
                        self.egl_surface = None

                    EGL.eglTerminate(self.egl_display)
                    self.egl_display = None
                    print('EGL context cleaned up')
            except Exception as e:
                print(f'Warning: Error cleaning up EGL: {e}')

        # Clean up GBM device, if any.
        if self.gbm_device is not None:
            try:
                gbm = CDLL('libgbm.so.1')
                gbm.gbm_device_destroy.argtypes = [c_void_p]
                gbm.gbm_device_destroy(c_void_p(self.gbm_device))
            except Exception as e:
                print(f'Warning: Error cleaning up GBM: {e}')
            finally:
                self.gbm_device = None

        # Close DRM file descriptor, if any.
        if self.drm_fd is not None:
            try:
                os.close(self.drm_fd)
            except Exception as e:
                print(f'Warning: Error closing DRM device: {e}')
            finally:
                self.drm_fd = None