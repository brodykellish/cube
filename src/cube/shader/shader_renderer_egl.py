"""
EGL-based shader renderer for Raspberry Pi LED matrix.

This implementation uses EGL for offscreen rendering on Raspberry Pi.
The rendered framebuffer is intended to be pulled and mixed with other
layers by the display utility.
"""

import os

# Configure PyOpenGL for EGL before importing
os.environ['PYOPENGL_PLATFORM'] = 'egl'

from OpenGL.GL import *
from OpenGL import EGL
from OpenGL.platform import PLATFORM
from ctypes import pointer, c_int, c_void_p, CDLL, c_char_p

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
        self.drm_fd = None
        self.gbm_device = None
        self.fbo = None
        self.fbo_texture = None

        super().__init__(width, height, scale=1)
        print(f"EGL shader renderer initialized: {width}×{height} (headless)")

    def make_context_current(self) -> bool:
        """Make this EGL context current."""
        if not self.egl_display or not self.egl_context or not self.egl_surface:
            return False

        try:
            result = EGL.eglMakeCurrent(
                self.egl_display,
                self.egl_surface,
                self.egl_surface,
                self.egl_context
            )
            return bool(result)
        except Exception as e:
            print(f"Error making EGL context current: {e}")
            return False
    
    def _init_context(self):
        """Initialize EGL context for offscreen rendering using GBM."""
        # Try to use GBM for proper EGL initialization on Raspberry Pi
        try:
            # Load GBM library
            gbm = CDLL('libgbm.so.1')

            # Open DRM device
            drm_card = '/dev/dri/card0'
            if not os.path.exists(drm_card):
                raise RuntimeError(f"DRM device {drm_card} not found")

            # Open DRM device (O_RDWR = 2, O_CLOEXEC = 0o2000000)
            self.drm_fd = os.open(drm_card, os.O_RDWR)

            # Create GBM device
            gbm.gbm_create_device.argtypes = [c_int]
            gbm.gbm_create_device.restype = c_void_p
            self.gbm_device = gbm.gbm_create_device(self.drm_fd)

            if not self.gbm_device:
                raise RuntimeError("Failed to create GBM device")

            # Get EGL display from GBM device using platform extension
            # EGL_PLATFORM_GBM_KHR = 0x31D7
            EGL_PLATFORM_GBM_KHR = 0x31D7

            # Try eglGetPlatformDisplay (EGL 1.5 / extension)
            try:
                eglGetPlatformDisplay = EGL.eglGetProcAddress(b'eglGetPlatformDisplayEXT')
                if eglGetPlatformDisplay:
                    self.egl_display = eglGetPlatformDisplay(
                        EGL_PLATFORM_GBM_KHR,
                        c_void_p(self.gbm_device),
                        None
                    )
                else:
                    # Fallback to eglGetDisplay with GBM device
                    self.egl_display = EGL.eglGetDisplay(c_void_p(self.gbm_device))
            except:
                # Fallback to eglGetDisplay with GBM device
                self.egl_display = EGL.eglGetDisplay(c_void_p(self.gbm_device))

            if self.egl_display == EGL.EGL_NO_DISPLAY:
                raise RuntimeError("Failed to get EGL display from GBM")

            print(f"Using GBM device for EGL display")

        except Exception as e:
            print(f"Warning: Could not use GBM ({e}), falling back to EGL_DEFAULT_DISPLAY")
            self.egl_display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
            if self.egl_display == EGL.EGL_NO_DISPLAY:
                raise RuntimeError("Failed to get EGL display")

        # Initialize EGL
        major = c_int()
        minor = c_int()
        if not EGL.eglInitialize(self.egl_display, pointer(major), pointer(minor)):
            error = EGL.eglGetError()
            raise RuntimeError(f"Failed to initialize EGL (error: 0x{error:x})")

        print(f"EGL initialized: version {major.value}.{minor.value}")

        # Bind OpenGL ES API first (required before choosing config on some implementations)
        if not EGL.eglBindAPI(EGL.EGL_OPENGL_ES_API):
            error = EGL.eglGetError()
            raise RuntimeError(f"Failed to bind OpenGL ES API (error: 0x{error:x})")

        # Try very minimal config first - Raspberry Pi can be picky
        config_attribs = [
            EGL.EGL_RENDERABLE_TYPE, EGL.EGL_OPENGL_ES2_BIT,
            EGL.EGL_SURFACE_TYPE, EGL.EGL_PBUFFER_BIT,
            EGL.EGL_NONE
        ]

        configs = (EGL.EGLConfig * 10)()
        num_configs = c_int()

        if not EGL.eglChooseConfig(
            self.egl_display,
            (c_int * len(config_attribs))(*config_attribs),
            configs,
            10,
            pointer(num_configs)
        ):
            error = EGL.eglGetError()
            raise RuntimeError(f"eglChooseConfig failed (error: 0x{error:x})")

        if num_configs.value == 0:
            # Try with absolutely no requirements except GLES2
            print("Warning: No configs found with PBuffer, trying any config...")
            config_attribs = [
                EGL.EGL_RENDERABLE_TYPE, EGL.EGL_OPENGL_ES2_BIT,
                EGL.EGL_NONE
            ]

            if not EGL.eglChooseConfig(
                self.egl_display,
                (c_int * len(config_attribs))(*config_attribs),
                configs,
                10,
                pointer(num_configs)
            ):
                error = EGL.eglGetError()
                raise RuntimeError(f"eglChooseConfig failed on retry (error: 0x{error:x})")

            if num_configs.value == 0:
                raise RuntimeError("Failed to find any compatible EGL config")

        print(f"Found {num_configs.value} compatible EGL config(s)")

        # Check if surfaceless contexts are supported (better for headless rendering on Pi)
        extensions = EGL.eglQueryString(self.egl_display, EGL.EGL_EXTENSIONS)
        supports_surfaceless = extensions and b'EGL_KHR_surfaceless_context' in extensions

        self.egl_surface = EGL.EGL_NO_SURFACE

        if not supports_surfaceless:
            # Need to create a PBuffer if surfaceless isn't supported
            pbuffer_attribs = [
                EGL.EGL_WIDTH, self.width,
                EGL.EGL_HEIGHT, self.height,
                EGL.EGL_NONE
            ]

            try:
                self.egl_surface = EGL.eglCreatePbufferSurface(
                    self.egl_display,
                    configs[0],
                    (c_int * len(pbuffer_attribs))(*pbuffer_attribs)
                )

                if self.egl_surface == EGL.EGL_NO_SURFACE:
                    error = EGL.eglGetError()
                    raise RuntimeError(f"Failed to create EGL pbuffer surface (error: 0x{error:x})")

                print("Created PBuffer surface for offscreen rendering")
            except Exception as e:
                raise RuntimeError(f"Failed to create PBuffer surface and surfaceless context not supported: {e}")
        else:
            print("Using surfaceless context for offscreen rendering")
        
        # Create OpenGL ES 3.0 context
        context_attribs = [
            EGL.EGL_CONTEXT_CLIENT_VERSION, 3,
            EGL.EGL_NONE
        ]

        self.egl_context = EGL.eglCreateContext(
            self.egl_display,
            configs[0],
            EGL.EGL_NO_CONTEXT,
            (c_int * len(context_attribs))(*context_attribs)
        )

        if self.egl_context == EGL.EGL_NO_CONTEXT:
            error = EGL.eglGetError()
            raise RuntimeError(f"Failed to create EGL context (error: 0x{error:x})")
        
        if not EGL.eglMakeCurrent(
            self.egl_display,
            self.egl_surface,
            self.egl_surface,
            self.egl_context
        ):
            error = EGL.eglGetError()
            raise RuntimeError(f"Failed to make EGL context current (error: 0x{error:x})")

        print("Created offscreen OpenGL context via EGL (headless)")

        # Register EGL context with PyOpenGL's platform
        # This is needed for PyOpenGL's context tracking to work properly
        try:
            PLATFORM.CurrentContextIsValid = lambda: True
            PLATFORM.GetCurrentContext = lambda: self.egl_context
        except Exception as e:
            print(f"Warning: Could not register EGL context with PyOpenGL platform: {e}")

        # Create FBO for offscreen rendering (required for surfaceless context)
        self._create_fbo()

    def _get_glsl_version(self) -> str:
        """Use OpenGL ES 3.00 for Raspberry Pi."""
        return "300 es"

    def _get_attribute_keyword(self) -> str:
        """Use 'in' keyword for GLSL ES 3.00."""
        return "in"

    def _get_precision_statement(self) -> str:
        """ES 3.00 still requires precision qualifiers."""
        return "precision mediump float;"

    def _create_fbo(self):
        """Create framebuffer object for offscreen rendering."""
        # Generate and bind FBO
        fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)

        # Create texture for color attachment (use RGBA for better OpenGL ES compatibility)
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        # Attach texture to FBO
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0)

        # Check FBO status
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"Framebuffer is not complete: 0x{status:x}")

        self.fbo = fbo
        self.fbo_texture = texture

        print(f"Created FBO {fbo} with texture {texture} ({self.width}x{self.height})")

    def _get_viewport_width(self) -> int:
        """Get viewport width."""
        return self.width
    
    def _get_viewport_height(self) -> int:
        """Get viewport height."""
        return self.height
    
    def _swap_buffers(self):
        """Swap buffers (no-op for offscreen rendering)."""
        # Ensure framebuffer rendering is complete
        glFlush()

    def render(self):
        """Render a frame, ensuring EGL context is current."""
        # Make sure EGL context is current before rendering
        if not EGL.eglMakeCurrent(
            self.egl_display,
            self.egl_surface,
            self.egl_surface,
            self.egl_context
        ):
            error = EGL.eglGetError()
            raise RuntimeError(f"Failed to make context current for render (error: 0x{error:x})")

        # Ensure FBO is bound for rendering
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        # Call parent render method
        super().render()

    def read_pixels(self):
        """Read pixels from FBO, ensuring proper binding."""
        import numpy as np

        # Make sure context is current
        if not EGL.eglMakeCurrent(
            self.egl_display,
            self.egl_surface,
            self.egl_surface,
            self.egl_context
        ):
            error = EGL.eglGetError()
            raise RuntimeError(f"Failed to make context current for read_pixels (error: 0x{error:x})")

        # Ensure FBO is bound for reading
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        # Read RGBA data (OpenGL ES requirement)
        pixel_data = glReadPixels(0, 0, self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE)

        # Convert to numpy array and flip vertically (OpenGL origin is bottom-left)
        pixels = np.frombuffer(pixel_data, dtype=np.uint8).reshape(self.height, self.width, 4)
        pixels = np.flipud(pixels)

        # Convert RGBA to RGB (drop alpha channel)
        return pixels[:, :, :3].copy()
    
    def cleanup(self):
        """Clean up EGL resources."""
        self.uniform_manager.cleanup()

        # Make context current before cleaning up OpenGL resources
        if self.egl_display is not None and self.egl_context is not None:
            try:
                EGL.eglMakeCurrent(
                    self.egl_display,
                    self.egl_surface,
                    self.egl_surface,
                    self.egl_context
                )
            except:
                pass

        # Finish all OpenGL commands before cleanup
        try:
            glFinish()
        except:
            pass

        # Clean up shader program
        if self.program is not None:
            try:
                glDeleteProgram(self.program)
                self.program = None
            except:
                pass

        # Clean up VBO
        if self.vbo is not None:
            try:
                glDeleteBuffers(1, [self.vbo])
                self.vbo = None
            except:
                pass

        # Clean up textures
        for tex_id in self.textures.values():
            if tex_id is not None:
                try:
                    glDeleteTextures([tex_id])
                except:
                    pass
        self.textures.clear()

        # Clean up FBO and texture
        if self.fbo is not None:
            try:
                glBindFramebuffer(GL_FRAMEBUFFER, 0)
                glDeleteFramebuffers(1, [self.fbo])
                self.fbo = None
            except:
                pass
        if self.fbo_texture is not None:
            try:
                glDeleteTextures([self.fbo_texture])
                self.fbo_texture = None
            except:
                pass

        if self.egl_display is not None:
            try:
                # Release the current context before destroying
                try:
                    EGL.eglMakeCurrent(
                        self.egl_display,
                        EGL.EGL_NO_SURFACE,
                        EGL.EGL_NO_SURFACE,
                        EGL.EGL_NO_CONTEXT
                    )
                except:
                    pass

                if self.egl_context is not None:
                    EGL.eglDestroyContext(self.egl_display, self.egl_context)
                    self.egl_context = None
                if self.egl_surface is not None and self.egl_surface != EGL.EGL_NO_SURFACE:
                    EGL.eglDestroySurface(self.egl_display, self.egl_surface)
                    self.egl_surface = None
                EGL.eglTerminate(self.egl_display)
                self.egl_display = None

                print("EGL context cleaned up")
            except Exception as e:
                print(f"Warning: Error cleaning up EGL: {e}")

        # Clean up GBM and DRM resources
        if self.gbm_device is not None:
            try:
                gbm = CDLL('libgbm.so.1')
                gbm.gbm_device_destroy.argtypes = [c_void_p]
                gbm.gbm_device_destroy(c_void_p(self.gbm_device))
                self.gbm_device = None
            except Exception as e:
                print(f"Warning: Error cleaning up GBM: {e}")

        if self.drm_fd is not None:
            try:
                os.close(self.drm_fd)
                self.drm_fd = None
            except Exception as e:
                print(f"Warning: Error closing DRM device: {e}")

