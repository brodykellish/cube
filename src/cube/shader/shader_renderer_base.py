"""
Base shader renderer with shared functionality.

This module contains the base class that is extended by platform-specific
implementations (GLUT for macOS, EGL for Raspberry Pi).
"""
import time
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from abc import ABC, abstractmethod
from OpenGL.GL import *
from OpenGL.GL import shaders
from .camera_modes import CameraMode, SphericalCamera
from .uniform_sources import UniformSourceManager, MouseUniformSource, UniformSource
from .shader_compiler import wrap_shadertoy_shader

class ShaderRendererBase(ABC):
    """\n    Base shader renderer with shared functionality.\n\n    Platform-specific implementations should inherit from this class\n    and implement the abstract methods for context creation.\n    """

    @abstractmethod
    def make_context_current(self) -> bool:
        """\n        Make this renderer\'s OpenGL context current for the calling thread.\n\n        This is required when using the renderer from a different thread than\n        where it was created (e.g., background shader validation).\n\n        Returns:\n            True if context was made current, False otherwise\n        """  # inserted
        return

    def __init__(self, width: int, height: int, scale: int=1):
        """\n        Initialize base shader renderer.\n        \n        Args:\n            width: Render width in pixels\n            height: Render height in pixels\n            scale: Window scale factor (platform-specific usage)\n        """  # inserted
        self.width = width
        self.height = height
        self.scale = scale
        self.start_time = time.time()
        self.frame_count = 0
        self.last_fps_time = self.start_time
        self.fps = 0.0
        self.fps_frames = 0
        self.uniform_manager = UniformSourceManager()
        self.mouse_source = MouseUniformSource(width, height)
        self.uniform_manager.add_source(self.mouse_source)
        self.program = None
        self.vao = None
        self.vbo = None
        self.uniform_locs = {}
        self.textures = {}
        print('Initializing context')
        self._init_context()
        print('Setting viewport')
        glViewport(0, 0, self._get_viewport_width(), self._get_viewport_height())
        print('Disabling depth test')
        glDisable(GL_DEPTH_TEST)
        print('Disabling dither')
        glDisable(GL_DITHER)
        self._create_fullscreen_quad()

    @abstractmethod
    def _init_context(self):
        """Initialize OpenGL context (platform-specific)."""  # inserted
        return

    @abstractmethod
    def _get_viewport_width(self) -> int:
        """Get viewport width (platform-specific)."""  # inserted
        return

    @abstractmethod
    def _get_viewport_height(self) -> int:
        """Get viewport height (platform-specific)."""  # inserted
        return

    @abstractmethod
    def _swap_buffers(self):
        """Swap buffers / present frame (platform-specific)."""  # inserted
        return

    @abstractmethod
    def cleanup(self):
        """Clean up platform-specific resources."""  # inserted
        return

    def _get_glsl_version(self) -> str:
        """
        Get the GLSL version string for this platform.

        Override in subclasses to specify platform-specific GLSL version.
        Default is OpenGL ES 1.0 (#version 100).
        """
        return '100'

    def _get_attribute_keyword(self) -> str:
        """
        Get the attribute keyword for this GLSL version.

        Returns 'attribute' for GLSL ES 100, 'in' for modern GLSL.
        """
        return 'attribute'

    def _get_precision_statement(self) -> str:
        """
        Get the precision statement for fragment shaders.

        Returns precision statement for GLSL ES, empty for desktop GLSL.
        """
        return 'precision mediump float;'

    def handle_events(self) -> bool:
        """\n        Handle platform-specific events (optional, for window lifecycle).\n        \n        Base implementation always returns True. Override in windowed implementations\n        to handle quit events.\n        \n        Returns:\n            False if quit requested, True otherwise\n        """  # inserted
        return True

    def _create_fullscreen_quad(self):
        """Create fullscreen quad for shader rendering."""  # inserted
        print('Creating fullscreen quad')
        gl_version_str = glGetString(GL_VERSION)
        needs_vao = False
        if gl_version_str:
            version_str = gl_version_str.decode()
            if 'core' in version_str.lower() or any((version_str.startswith(f'{major}.') for major in range(3, 10))):
                needs_vao = True
        if needs_vao:
            self.vao = glGenVertexArrays(1)
            glBindVertexArray(self.vao)
            print(f'VAO: {self.vao}')
        vertices = np.array([(-1.0), (-1.0), 1.0, (-1.0), (-1.0), 1.0, 1.0, 1.0], dtype=np.float32)
        print(f'Vertices: {vertices}')
        self.vbo = glGenBuffers(1)
        print(f'VBO: {self.vbo}')
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        print(f'Buffer data: {vertices.nbytes}')
        if needs_vao:
            glBindVertexArray(self.vao)

    def _load_texture(self, image_path: str) -> Optional[int]:
        """Load an image file and create an OpenGL texture."""  # inserted
        from PIL import Image
        try:
            img = Image.open(image_path).convert('RGB')
            img_data = np.array(img, dtype=np.uint8)
            img_data = np.flip(img_data, axis=0).copy()
            img_data = np.ascontiguousarray(img_data)
            texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, img.width, img.height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
            print(f'Loaded texture: {image_path} ({img.width}×{img.height})')
            return texture_id
        except Exception as e:
            print(f'Warning: Failed to load texture {image_path}: {e}')
            return None

    def _load_shader_textures(self, shader_path: str):
        """Load textures for a shader based on naming convention."""  # inserted
        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()
        shader_dir = Path(shader_path).parent
        shader_name = Path(shader_path).stem
        for channel in range(4):
            for ext in ['', '.png', '.jpg', '.jpeg', '.bmp']:
                texture_path = shader_dir / f'{shader_name}.channel{channel}{ext}'
                if texture_path.exists():
                    texture_id = self._load_texture(str(texture_path))
                    if texture_id is not None:
                        self.textures[channel] = texture_id
                    break

    def load_shader(self, shader_path: str):
        """Load and compile a Shadertoy-format GLSL shader."""
        path = Path(shader_path)
        if not path.exists():
            raise FileNotFoundError(f'Shader file not found: {path}')
        with open(path, 'r') as f:
            fragment_source = f.read()
        glsl_version = self._get_glsl_version()
        precision_statement = self._get_precision_statement()
        vertex_source, fragment_wrapped = wrap_shadertoy_shader(
            fragment_source,
            glsl_version=glsl_version,
            precision_statement=precision_statement,
        )
        if not self.make_context_current():
            raise RuntimeError('Failed to make OpenGL context current for shader compilation')
        if hasattr(self, 'vao') and self.vao:
            glBindVertexArray(self.vao)
        try:
            vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
            program = shaders.compileProgram(vertex_shader, fragment_shader)
        except RuntimeError as e:
            raise RuntimeError(f'Shader compilation failed: {e}') from e

        self.program = program
        glUseProgram(self.program)
        self.uniform_locs = {}
        num_uniforms = glGetProgramiv(self.program, GL_ACTIVE_UNIFORMS)
        for i in range(num_uniforms):
            name, size, type_ = glGetActiveUniform(self.program, i)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            name = name.rstrip('\x00')
            loc = glGetUniformLocation(self.program, name.encode('ascii'))
            if loc >= 0:
                self.uniform_locs[name] = loc

        print(f'Registered {len(self.uniform_locs)} shader uniforms: {list(self.uniform_locs.keys())}')
        if 'iResolution' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iResolution'], float(self.width), float(self.height), 1.0)
        self.mouse_source.set_resolution(self.width, self.height)
        for i in range(4):
            channel_name = f'iChannel{i}'
            if channel_name in self.uniform_locs:
                glUniform1i(self.uniform_locs[channel_name], i)
        self._load_shader_textures(str(path))
        print(f'Shader loaded: {shader_path}')

    def add_uniform_source(self, source: UniformSource):
        """Add an uniform source to the renderer."""  # inserted
        self.uniform_manager.add_source(source)

    def remove_uniform_source(self, source: UniformSource):
        """Remove an uniform source from the renderer."""  # inserted
        self.uniform_manager.remove_source(source)

    def get_camera_source(self):
        """Get the camera uniform source (if one is added)."""  # inserted
        from .camera_uniform_source import CameraUniformSource
        for source in self.uniform_manager.sources:
            if isinstance(source, CameraUniformSource):
                return source
        else:  # inserted
            return
    
    def get_mouse_source(self):
        """Get the mouse uniform source."""
        return self.mouse_source

    def set_camera_mode(self, camera: CameraMode):
        """Set camera mode via camera uniform source."""  # inserted
        camera_source = self.get_camera_source()
        if camera_source:
            camera_source.camera = camera
            camera_source.last_update_time = time.time()

    def reset_camera(self):
        """Reset camera to default position."""  # inserted
        camera_source = self.get_camera_source()
        if camera_source:
            camera_source.reset_camera()
    
    def update_mouse(self, x: float, y: float, button_pressed: bool = False):
        """
        Update mouse state.
        
        Args:
            x: Mouse x position in pixels
            y: Mouse y position in pixels
            button_pressed: True if mouse button is pressed
        """
        self.mouse_source.set_mouse_position(x, y)
        self.mouse_source.set_mouse_button(button_pressed)

    def render(self):
        """Render one frame of the shader."""  # inserted
        if not self.program:
            raise RuntimeError('No shader loaded. Call load_shader() first.')
        elapsed = time.time() - self.start_time
        dt = elapsed - self.frame_count / 60.0 if self.frame_count > 0 else 0.016
        self.uniform_manager.update(dt)
        uniforms = self.uniform_manager.get_all_uniforms()
        uniforms['iTime'] = elapsed
        uniforms['iFrame'] = self.frame_count
        uniforms['iResolution'] = (float(self.width), float(self.height), 1.0)
        glUseProgram(self.program)
        for name, value in uniforms.items():
            if name not in self.uniform_locs:
                continue
            loc = self.uniform_locs[name]
            if isinstance(value, (tuple, list)):
                if len(value) == 2:
                    glUniform2f(loc, *value)
                else:  # inserted
                    if len(value) == 3:
                        glUniform3f(loc, *value)
                    else:  # inserted
                        if len(value) == 4:
                            glUniform4f(loc, *value)
            else:  # inserted
                if isinstance(value, int):
                    glUniform1i(loc, value)
                else:  # inserted
                    if isinstance(value, float):
                        glUniform1f(loc, value)
        for i in range(4):
            if i in self.textures and self.textures[i] is not None:
                glActiveTexture(GL_TEXTURE0 + i)
                glBindTexture(GL_TEXTURE_2D, self.textures[i])
        glClear(GL_COLOR_BUFFER_BIT)
        if hasattr(self, 'vao') and self.vao:
            glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        pos_attrib = glGetAttribLocation(self.program, b'position')
        glEnableVertexAttribArray(pos_attrib)
        glVertexAttribPointer(pos_attrib, 2, GL_FLOAT, GL_FALSE, 0, None)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glDisableVertexAttribArray(pos_attrib)
        if hasattr(self, 'vao') and self.vao:
            glBindVertexArray(0)
        self._swap_buffers()
        self.frame_count += 1
        self.fps_frames += 1
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.fps = self.fps_frames / (current_time - self.last_fps_time)
            self.last_fps_time = current_time
            self.fps_frames = 0

    def read_pixels(self) -> np.ndarray:
        """Read rendered pixels from OpenGL framebuffer."""  # inserted
        pixel_data = glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE)
        frame = np.frombuffer(pixel_data, dtype=np.uint8)
        frame = frame.reshape((self.height, self.width, 3))
        frame = np.flip(frame, axis=0).copy()
        return frame

    def get_stats(self) -> dict:
        """Get rendering statistics."""  # inserted
        elapsed = time.time() - self.start_time
        avg_fps = self.frame_count / elapsed if elapsed > 0 else 0
        return {'frames': self.frame_count, 'elapsed': elapsed, 'avg_fps': avg_fps, 'current_fps': self.fps}

    def __del__(self):
        """Destructor."""  # inserted
        try:
            self.cleanup()
        except:
            return