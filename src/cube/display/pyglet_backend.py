"""
Pyglet display backend for development on macOS/Linux/Windows.

Simple OpenGL texture rendering with HiDPI support and optional scaling.
"""
import pyglet
pyglet.options['dpi_scale'] = 'real'
import numpy as np
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
        
        self.window = pyglet.window.Window(
            width=self.window_width,
            height=self.window_height,
            caption=title,
            resizable=resizable,
            vsync=False,  # disable vsync so FPS is not clamped to display refresh
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
        flipped = np.flip(framebuffer, axis=0)
        self.window.switch_to()
        # Ensure viewport covers the full framebuffer each frame. Other parts
        # of the system (e.g. FBO rendering) may have changed the viewport.
        glViewport(0, 0, self.fb_width, self.fb_height)
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.program)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, flipped.shape[1], flipped.shape[0], GL_RGB, GL_UNSIGNED_BYTE, flipped)
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
            'paste': keyboard_state.paste_text
        }
        return result

    def close(self):
        """Clean up pyglet resources"""
        self.keyboard.cleanup()
        self.window.switch_to()
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
        if self.texture:
            glDeleteTextures([self.texture])
        if self.program:
            glDeleteProgram(self.program)
        self.window.close()
