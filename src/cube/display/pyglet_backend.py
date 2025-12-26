"""
Pyglet display backend for development on macOS/Linux/Windows.

Simple OpenGL texture rendering with HiDPI support and optional scaling.
"""
import pyglet
pyglet.options['dpi_scale'] = 'real'
import numpy as np
import time
from OpenGL.GL import *
from .backend import Backend
from ..input.pyglet_keyboard import PygletKeyboard


class PygletBackend(Backend):
    """Pyglet backend with OpenGL texture rendering"""

    def __init__(self, width: int, height: int, scale: int=1, title: str='Cube Control', resizable: bool=False, **kwargs):
        """
        Initialize pyglet backend.

        Args:
            width: Window width in pixels
            height: Window height in pixels
            scale: Render scale factor (1 = full res, 2 = half res, etc.)
            title: Window title
            resizable: Whether window can be resized
            **kwargs: Additional arguments (ignored)
        """
        print(f"Initializing Pyglet backend: {width}×{height}, scale={scale}, title='{title}'")
        self.window_width = width
        self.window_height = height
        self.scale = scale
        self._resize_pending = False
        self._is_fullscreen = False
        self._fullscreen_transitioning = False
        
        # Create window initially invisible to prevent it from stealing focus
        # It will be made visible when rendering starts
        self.window = pyglet.window.Window(
            width=self.window_width,
            height=self.window_height,
            caption=title,
            resizable=resizable,
            vsync=False,  # disable vsync so FPS is not clamped to display refresh
            visible=False,  # Start invisible to avoid stealing focus from menu
        )
        print(f'Pyglet window created: {self.window_width}×{self.window_height}')
        
        fb_width, fb_height = self.window.get_framebuffer_size()
        self.fb_width = fb_width
        self.fb_height = fb_height
        print(f'Framebuffer size: {fb_width}×{fb_height}')
        
        self._width = fb_width // scale
        self._height = fb_height // scale
        print(f'Render resolution: {self._width}×{self._height} (scale {scale}x)')
        
        gl_version = self.window.context.get_info().get_version()
        gl_renderer = self.window.context.get_info().get_renderer()
        print(f'OpenGL Version: {gl_version}')
        print(f'OpenGL Renderer: {gl_renderer}')
        
        if resizable:
            @self.window.event
            def on_resize(width, height):
                self._resize_pending = True
                self._handle_resize(width, height)
        
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.mouse_button_pressed = False
        
        @self.window.event
        def on_mouse_motion(x, y, dx, dy):
            scale_x = self._width / self.window_width if self.window_width > 0 else 1.0
            scale_y = self._height / self.window_height if self.window_height > 0 else 1.0
            self.mouse_x = float(x * scale_x)
            self.mouse_y = float((self.window.height - y) * scale_y)
        
        @self.window.event
        def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
            scale_x = self._width / self.window_width if self.window_width > 0 else 1.0
            scale_y = self._height / self.window_height if self.window_height > 0 else 1.0
            self.mouse_x = float(x * scale_x)
            self.mouse_y = float((self.window.height - y) * scale_y)
        
        @self.window.event
        def on_mouse_press(x, y, button, modifiers):
            scale_x = self._width / self.window_width if self.window_width > 0 else 1.0
            scale_y = self._height / self.window_height if self.window_height > 0 else 1.0
            self.mouse_x = float(x * scale_x)
            self.mouse_y = float((self.window.height - y) * scale_y)
            self.mouse_button_pressed = True
        
        @self.window.event
        def on_mouse_release(x, y, button, modifiers):
            scale_x = self._width / self.window_width if self.window_width > 0 else 1.0
            scale_y = self._height / self.window_height if self.window_height > 0 else 1.0
            self.mouse_x = float(x * scale_x)
            self.mouse_y = float((self.window.height - y) * scale_y)
            self.mouse_button_pressed = False
        
        self.keyboard = PygletKeyboard(self.window)
        self.texture = None
        self.vao = None
        self.vbo = None
        self.program = None
        self._init_gl_resources()

    @property
    def width(self) -> int:
        """Current render width"""
        return self._width

    @property
    def height(self) -> int:
        """Current render height"""
        return self._height
    
    def get_render_resolution(self) -> tuple[int, int]:
        """
        Get the shader rendering resolution.
        
        Returns:
            Tuple of (width, height) in pixels
        """
        return (self._width, self._height)
    
    def get_window_size(self) -> tuple[int, int]:
        """
        Get the window size (not framebuffer size).
        
        Returns:
            Tuple of (width, height) in pixels
        """
        return (self.window_width, self.window_height)
    
    def get_framebuffer_size(self) -> tuple[int, int]:
        """
        Get the framebuffer size (may differ from window size on HiDPI displays).
        
        Returns:
            Tuple of (width, height) in pixels
        """
        return (self.fb_width, self.fb_height)
    
    def set_fullscreen(self, fullscreen: bool):
        """
        Toggle fullscreen mode.
        
        Args:
            fullscreen: True to enter fullscreen, False to exit
        """
        if fullscreen and not self._is_fullscreen:
            # Mark that we're transitioning to prevent rendering during transition
            self._fullscreen_transitioning = True
            
            # Save current window size before going fullscreen
            self._saved_window_size = (self.window_width, self.window_height)
            try:
                self.window.set_fullscreen(True)
            except Exception as e:
                print(f"[Pyglet] Error setting fullscreen: {e}")
                self._fullscreen_transitioning = False
                return
            
            # Wait a moment for window to finish transitioning
            # This gives the render loop time to finish any in-flight OpenGL operations
            time.sleep(0.2)
            
            self.window_width, self.window_height = self.window.size
            # Update framebuffer size after fullscreen change
            fb_width, fb_height = self.window.get_framebuffer_size()
            self.fb_width = fb_width
            self.fb_height = fb_height
            self._width = fb_width // self.scale
            self._height = fb_height // self.scale
            self._is_fullscreen = True
            
            # Update viewport and texture size (ensure context is current)
            self.window.switch_to()
            error = glGetError()
            if error != GL_NO_ERROR:
                print(f"[Pyglet] OpenGL error before fullscreen setup: {error}")
            
            glViewport(0, 0, fb_width, fb_height)
            if self.texture and self.texture != 0:
                try:
                    glBindTexture(GL_TEXTURE_2D, self.texture)
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self._width, self._height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
                    error = glGetError()
                    if error != GL_NO_ERROR:
                        print(f"[Pyglet] OpenGL error resizing texture in fullscreen: {error}")
                except Exception as e:
                    print(f"[Pyglet] Exception resizing texture in fullscreen: {e}")
            self._fullscreen_transitioning = False
            print(f"[Pyglet] Entered fullscreen: window {self.window_width}×{self.window_height}, framebuffer {fb_width}×{fb_height}, render {self._width}×{self._height}")
        elif not fullscreen and self._is_fullscreen:
            # Mark that we're transitioning to prevent rendering during transition
            self._fullscreen_transitioning = True
            
            # Restore saved window size
            if hasattr(self, '_saved_window_size'):
                restore_width, restore_height = self._saved_window_size
            else:
                restore_width, restore_height = 960, 540  # Default fallback
            try:
                self.window.set_fullscreen(False)
            except Exception as e:
                print(f"[Pyglet] Error exiting fullscreen: {e}")
                self._fullscreen_transitioning = False
                return
            
            # Wait a moment for window to finish transitioning
            # This gives the render loop time to finish any in-flight OpenGL operations
            time.sleep(0.2)
            
            self.window.set_size(restore_width, restore_height)
            self.window_width, self.window_height = self.window.size
            # Update framebuffer size after windowed change
            fb_width, fb_height = self.window.get_framebuffer_size()
            self.fb_width = fb_width
            self.fb_height = fb_height
            self._width = fb_width // self.scale
            self._height = fb_height // self.scale
            self._is_fullscreen = False
            
            # Update viewport and texture size (ensure context is current)
            self.window.switch_to()
            error = glGetError()
            if error != GL_NO_ERROR:
                print(f"[Pyglet] OpenGL error before windowed setup: {error}")
            
            glViewport(0, 0, fb_width, fb_height)
            if self.texture and self.texture != 0:
                try:
                    glBindTexture(GL_TEXTURE_2D, self.texture)
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self._width, self._height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
                    error = glGetError()
                    if error != GL_NO_ERROR:
                        print(f"[Pyglet] OpenGL error resizing texture in windowed: {error}")
                except Exception as e:
                    print(f"[Pyglet] Exception resizing texture in windowed: {e}")
            self._fullscreen_transitioning = False
            print(f"[Pyglet] Exited fullscreen: window {self.window_width}×{self.window_height}, framebuffer {fb_width}×{fb_height}, render {self._width}×{self._height}")

    def was_resized(self) -> bool:
        """Check and clear resize flag"""
        if self._resize_pending:
            self._resize_pending = False
            return True
        return False

    def _handle_resize(self, window_w: int, window_h: int):
        """Handle window resize event"""
        fb_w, fb_h = self.window.get_framebuffer_size()
        self.fb_width = fb_w
        self.fb_height = fb_h
        self._width = fb_w // self.scale
        self._height = fb_h // self.scale
        print(f'Window resized: {window_w}×{window_h} → render {self._width}×{self._height}')
        self.window.switch_to()
        glViewport(0, 0, fb_w, fb_h)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self._width, self._height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)

    def _init_gl_resources(self):
        """Initialize modern OpenGL resources (shaders, VAO, VBO, texture)."""
        self.window.switch_to()
        glViewport(0, 0, self.fb_width, self.fb_height)
        glClearColor(1.0, 1.0, 1.0, 1.0)
        
        vertex_shader = """
        #version 410
        in vec2 position;
        out vec2 texcoord;

        void main() {
            gl_Position = vec4(position, 0.0, 1.0);
            texcoord.x = (position.x + 1.0) / 2.0;
            texcoord.y = (position.y + 1.0) / 2.0;
        }
        """
        
        fragment_shader = """
        #version 410
        uniform sampler2D tex;
        in vec2 texcoord;
        out vec4 FragColor;

        void main() {
            FragColor = texture(tex, texcoord);
        }
        """
        
        vs = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vs, vertex_shader)
        glCompileShader(vs)
        if not glGetShaderiv(vs, GL_COMPILE_STATUS):
            print(f'Vertex shader compile error: {glGetShaderInfoLog(vs).decode()}')
        
        fs = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fs, fragment_shader)
        glCompileShader(fs)
        if not glGetShaderiv(fs, GL_COMPILE_STATUS):
            print(f'Fragment shader compile error: {glGetShaderInfoLog(fs).decode()}')
        
        self.program = glCreateProgram()
        glAttachShader(self.program, vs)
        glAttachShader(self.program, fs)
        glLinkProgram(self.program)
        if not glGetProgramiv(self.program, GL_LINK_STATUS):
            print(f'Program link error: {glGetProgramInfoLog(self.program).decode()}')
        
        glDeleteShader(vs)
        glDeleteShader(fs)
        
        quad_vertices = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype=np.float32)
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)
        
        glUseProgram(self.program)
        pos_attr = glGetAttribLocation(self.program, 'position')
        glEnableVertexAttribArray(pos_attr)
        glVertexAttribPointer(pos_attr, 2, GL_FLOAT, GL_FALSE, 0, None)
        glBindVertexArray(0)
        
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self._width, self._height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        
        glUseProgram(self.program)
        tex_loc = glGetUniformLocation(self.program, 'tex')
        glUniform1i(tex_loc, 0)
        glUseProgram(0)

    def display(self, framebuffer: np.ndarray):
        """
        Display framebuffer via pyglet.

        Args:
            framebuffer: RGB framebuffer (H, W, 3)
        """
        # Skip display during fullscreen transitions to avoid OpenGL/Metal errors
        if self._fullscreen_transitioning:
            return
        
        flipped = np.flip(framebuffer, axis=0)
        fb_height, fb_width = flipped.shape[:2]
        
        # Ensure context is current before any OpenGL operations
        try:
            self.window.switch_to()
        except Exception as e:
            print(f"[Pyglet] Error switching to context: {e}")
            return
        
        # Check for OpenGL errors before proceeding
        error = glGetError()
        if error != GL_NO_ERROR:
            print(f"[Pyglet] OpenGL error before display: {error}")
        
        # Ensure viewport covers the full framebuffer each frame. Other parts
        # of the system (e.g. FBO rendering) may have changed the viewport.
        glViewport(0, 0, self.fb_width, self.fb_height)
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.program)
        glActiveTexture(GL_TEXTURE0)
        
        # Check if texture needs to be resized (but skip during fullscreen transition)
        if not self._fullscreen_transitioning and (fb_width != self._width or fb_height != self._height):
            # Recreate texture with new dimensions
            # Ensure context is current and texture is valid before deletion
            if self.texture is not None and self.texture != 0:
                try:
                    glBindTexture(GL_TEXTURE_2D, 0)  # Unbind first
                    glDeleteTextures([self.texture])
                    error = glGetError()
                    if error != GL_NO_ERROR:
                        print(f"[Pyglet] Error deleting texture: {error}")
                except Exception as e:
                    print(f"[Pyglet] Exception deleting texture: {e}")
            
            # Ensure context is still current before creating new texture
            self.window.switch_to()
            try:
                self.texture = glGenTextures(1)
                error = glGetError()
                if error != GL_NO_ERROR:
                    print(f"[Pyglet] Error generating texture: {error}")
                    # If texture creation failed, try to continue with existing texture
                    if self.texture is None or self.texture == 0:
                        print("[Pyglet] Failed to create texture, skipping frame")
                        return
            except Exception as e:
                print(f"[Pyglet] Exception generating texture: {e}")
                return
            
            glBindTexture(GL_TEXTURE_2D, self.texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, fb_width, fb_height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
            self._width = fb_width
            self._height = fb_height
        else:
            glBindTexture(GL_TEXTURE_2D, self.texture)
        
        # Only proceed if texture is valid
        if self.texture is None or self.texture == 0:
            print("[Pyglet] Invalid texture, skipping frame")
            return
        
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, fb_width, fb_height, GL_RGB, GL_UNSIGNED_BYTE, flipped)
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glBindVertexArray(0)
        glUseProgram(0)
        self.window.flip()

    def poll(self) -> dict:
        """Poll pyglet events and keyboard state"""
        self.window.dispatch_events()
        keyboard_state = self.keyboard.poll()
        result = {
            'quit': keyboard_state.quit,
            'key': keyboard_state.key_press,
            'keys': keyboard_state.keys_held,
            'paste': keyboard_state.paste_text,
            'mouse': {
                'x': self.mouse_x,
                'y': self.mouse_y,
                'button_pressed': self.mouse_button_pressed
            }
        }
        return result

    def close(self):
        """Clean up pyglet resources"""
        self.keyboard.cleanup()
        
        # Try to clean up OpenGL resources, but handle errors gracefully
        # The context might be invalid or resources might already be deleted
        context_valid = False
        try:
            # Check if window and context are still valid
            if hasattr(self, 'window') and self.window and not self.window.has_exit:
                try:
                    self.window.switch_to()
                    context_valid = True
                except Exception as e:
                    print(f"[Pyglet] Cannot switch to window context (may be destroyed): {e}")
                    context_valid = False
            
            if context_valid:
                # Clear any pending OpenGL errors
                while glGetError() != GL_NO_ERROR:
                    pass
                
                if self.vao and self.vao != 0:
                    try:
                        glDeleteVertexArrays(1, [self.vao])
                        error = glGetError()
                        if error != GL_NO_ERROR:
                            print(f"[Pyglet] Error deleting VAO: {error}")
                    except Exception as e:
                        print(f"[Pyglet] Exception deleting VAO: {e}")
                
                if self.vbo and self.vbo != 0:
                    try:
                        glDeleteBuffers(1, [self.vbo])
                        error = glGetError()
                        if error != GL_NO_ERROR:
                            print(f"[Pyglet] Error deleting VBO: {error}")
                    except Exception as e:
                        print(f"[Pyglet] Exception deleting VBO: {e}")
                
                if self.texture and self.texture != 0:
                    try:
                        glDeleteTextures([self.texture])
                        error = glGetError()
                        if error != GL_NO_ERROR:
                            print(f"[Pyglet] Error deleting texture: {error}")
                    except Exception as e:
                        print(f"[Pyglet] Exception deleting texture: {e}")
                
                if self.program and self.program != 0:
                    try:
                        glDeleteProgram(self.program)
                        error = glGetError()
                        if error != GL_NO_ERROR:
                            # Don't print error for invalid program - it might already be deleted
                            if error != 1281:  # GL_INVALID_VALUE
                                print(f"[Pyglet] Error deleting program: {error}")
                    except Exception as e:
                        print(f"[Pyglet] Exception deleting program: {e}")
        except Exception as e:
            print(f"[Pyglet] Error during OpenGL cleanup: {e}")
        finally:
            # Always try to close window, even if cleanup failed
            if hasattr(self, 'window') and self.window:
                try:
                    self.window.close()
                except Exception as e:
                    print(f"[Pyglet] Error closing window: {e}")
