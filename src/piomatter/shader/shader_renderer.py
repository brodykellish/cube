"""
Unified standalone shader renderer with input abstraction.

This is a standalone version of the shader renderer that uses the InputManager
system for clean separation of concerns. It can be used independent of the
menu system and provides a complete shader rendering solution.
"""

import time
import numpy as np
from pathlib import Path
from typing import Optional

try:
    import pygame
    from pygame.locals import *
    from OpenGL.GL import *
    from OpenGL.GL import shaders
except ImportError as e:
    raise ImportError(
        "Shader renderer requires pygame and PyOpenGL. "
        "Install with: pip install pygame PyOpenGL PyOpenGL_accelerate"
    ) from e

from .camera_modes import CameraMode, SphericalCamera, StaticCamera
from .input_sources import InputManager, KeyboardInput, InputSource


class ShaderRenderer:
    """
    Unified standalone shader renderer with input abstraction.

    Features:
    - Offscreen or windowed OpenGL rendering (GLUT/EGL or pygame)
    - InputManager for clean input handling (keyboard, audio, camera, etc.)
    - Camera mode system for different navigation paradigms
    - Shadertoy-compatible shader format
    - Automatic texture loading
    - FPS monitoring
    """

    def __init__(self, width: int, height: int, windowed: bool = False, scale: int = 1):
        """
        Initialize unified shader renderer.

        Args:
            width: Render width in pixels
            height: Render height in pixels
            windowed: If True, create pygame window; if False, offscreen context
            scale: Window scale factor (only for windowed mode)
        """
        self.width = width
        self.height = height
        self.windowed = windowed
        self.scale = scale
        self.start_time = time.time()
        self.frame_count = 0
        self.last_fps_time = self.start_time
        self.fps = 0.0
        self.fps_frames = 0

        # Input manager (handles all input sources)
        self.input_manager = InputManager()

        # Create keyboard input source by default
        self.keyboard_input = KeyboardInput()
        self.input_manager.add_source(self.keyboard_input)

        # Camera mode system
        self.camera_mode = SphericalCamera(
            distance=12.0,
            yaw=0.785,  # ~45 degrees
            pitch=0.6,  # ~34 degrees
            rotate_speed=1.5,
            zoom_speed=5.0,
            damping=0.9
        )

        # Shift key state (for camera mode modifiers)
        self.shift_pressed = False

        # Create OpenGL context
        if windowed:
            self._init_windowed()
        else:
            self._init_offscreen()

        # OpenGL setup
        if windowed:
            glViewport(0, 0, width * scale, height * scale)
        else:
            glViewport(0, 0, width, height)

        glDisable(GL_DEPTH_TEST)
        glDisable(GL_DITHER)

        # Shader program
        self.program = None
        self.vbo = None

        # Uniform locations (will be set when shader is loaded)
        self.uniform_locs = {}

        # Texture management
        self.textures = {}  # Maps channel index to texture ID

        # Context tracking
        self.context_type = None  # 'pygame', 'glut', or 'egl'

        # EGL-specific (for offscreen)
        self.egl_display = None
        self.egl_context = None
        self.egl_surface = None

        # Create fullscreen quad
        self._create_fullscreen_quad()

        print(f"Unified shader renderer initialized: {width}×{height} ({'windowed' if windowed else 'offscreen'})")

    def _init_windowed(self):
        """Initialize pygame window for windowed mode."""
        pygame.init()
        pygame.display.set_caption("Shader Renderer")

        self.screen = pygame.display.set_mode(
            (self.width * self.scale, self.height * self.scale),
            DOUBLEBUF | OPENGL
        )

        self.context_type = 'pygame'
        print("Created pygame window")

    def _init_offscreen(self):
        """Initialize offscreen OpenGL context (GLUT or EGL)."""
        # Try GLUT first
        if self._try_init_glut():
            return

        # Fall back to EGL
        if self._try_init_egl():
            return

        raise RuntimeError(
            "Failed to create OpenGL context. "
            "Tried GLUT (requires X11) and EGL (headless). "
            "Install freeglut3 or ensure EGL is available."
        )

    def _try_init_glut(self) -> bool:
        """Try to create OpenGL context using GLUT."""
        try:
            from OpenGL.GLUT import (
                glutInit, glutInitDisplayMode, glutInitWindowSize,
                glutCreateWindow, glutHideWindow, glutDisplayFunc,
                GLUT_RGBA, GLUT_DOUBLE, GLUT_DEPTH
            )

            try:
                glutInit()
            except:
                pass  # Already initialized

            glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
            glutInitWindowSize(self.width, self.height)
            self.glut_window = glutCreateWindow(b"Shader Renderer")

            def dummy_display():
                pass
            glutDisplayFunc(dummy_display)

            glutHideWindow()

            self.context_type = 'glut'
            print("Created offscreen OpenGL context via GLUT")
            return True

        except (ImportError, Exception) as e:
            print(f"GLUT initialization failed: {e}, trying EGL...")
            return False

    def _try_init_egl(self) -> bool:
        """Try to create OpenGL context using EGL (headless)."""
        try:
            from OpenGL import EGL
            from ctypes import pointer, c_int

            self.egl_display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
            if self.egl_display == EGL.EGL_NO_DISPLAY:
                return False

            major = c_int()
            minor = c_int()
            if not EGL.eglInitialize(self.egl_display, pointer(major), pointer(minor)):
                return False

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
                return False

            if not EGL.eglBindAPI(EGL.EGL_OPENGL_API):
                return False

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
                return False

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
                return False

            if not EGL.eglMakeCurrent(
                self.egl_display,
                self.egl_surface,
                self.egl_surface,
                self.egl_context
            ):
                return False

            self.context_type = 'egl'
            print("Created offscreen OpenGL context via EGL (headless)")
            return True

        except (ImportError, Exception) as e:
            print(f"EGL initialization failed: {e}")
            return False

    def _create_fullscreen_quad(self):
        """Create fullscreen quad for shader rendering."""
        vertices = np.array([
            -1.0, -1.0,
            1.0, -1.0,
            -1.0, 1.0,
            1.0, 1.0,
        ], dtype=np.float32)

        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

    def _load_texture(self, image_path: str) -> int:
        """Load an image file and create an OpenGL texture."""
        from PIL import Image

        try:
            img = Image.open(image_path).convert('RGB')
            img_data = np.array(img, dtype=np.uint8)

            texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture_id)

            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGB,
                img.width, img.height, 0,
                GL_RGB, GL_UNSIGNED_BYTE, img_data
            )

            print(f"Loaded texture: {image_path} ({img.width}×{img.height})")
            return texture_id

        except Exception as e:
            print(f"Warning: Failed to load texture {image_path}: {e}")
            return None

    def _load_shader_textures(self, shader_path: str):
        """Load textures for a shader based on naming convention."""
        # Clear existing textures
        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()

        shader_dir = Path(shader_path).parent
        shader_name = Path(shader_path).stem

        # Try to load textures for channels 0-3
        for channel in range(4):
            for ext in ['', '.png', '.jpg', '.jpeg', '.bmp']:
                texture_path = shader_dir / f"{shader_name}.channel{channel}{ext}"
                if texture_path.exists():
                    texture_id = self._load_texture(str(texture_path))
                    if texture_id is not None:
                        self.textures[channel] = texture_id
                    break

    def load_shader(self, shader_path: str):
        """Load and compile a Shadertoy-format GLSL shader."""
        path = Path(shader_path)
        if not path.exists():
            raise FileNotFoundError(f"Shader file not found: {path}")

        with open(path, 'r') as f:
            fragment_source = f.read()

        # Vertex shader
        vertex_source = """#version 120
attribute vec2 position;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}
"""

        # Fragment shader wrapper with all Shadertoy uniforms
        fragment_wrapped = f"""#version 120
uniform vec3 iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int iFrame;
uniform vec4 iMouse;
uniform vec4 iInput;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform sampler2D iChannel2;
uniform sampler2D iChannel3;
uniform vec3 iCameraPos;
uniform vec3 iCameraRight;
uniform vec3 iCameraUp;
uniform vec3 iCameraForward;
uniform float iBPM;
uniform float iBeatPhase;
uniform float iBeatPulse;
uniform float iAudioLevel;
uniform vec4 iAudioSpectrum;

#define texture texture2D

float tanh(float x) {{
    float e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}}

vec2 tanh(vec2 x) {{
    vec2 e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}}

vec3 tanh(vec3 x) {{
    vec3 e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}}

vec4 tanh(vec4 x) {{
    vec4 e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}}

float round(float x) {{
    return floor(x + 0.5);
}}

vec2 round(vec2 x) {{
    return floor(x + 0.5);
}}

vec3 round(vec3 x) {{
    return floor(x + 0.5);
}}

vec4 round(vec4 x) {{
    return floor(x + 0.5);
}}

{fragment_source}

void main() {{
    mainImage(gl_FragColor, gl_FragCoord.xy);
}}
"""

        # Compile shaders
        try:
            vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
            self.program = shaders.compileProgram(vertex_shader, fragment_shader)
        except RuntimeError as e:
            raise RuntimeError(f"Shader compilation failed: {e}")

        # Get uniform locations
        glUseProgram(self.program)

        uniform_names = [
            'iTime', 'iFrame', 'iResolution', 'iMouse', 'iInput',
            'iCameraPos', 'iCameraRight', 'iCameraUp', 'iCameraForward',
            'iChannel0', 'iChannel1', 'iChannel2', 'iChannel3',
            'iBPM', 'iBeatPhase', 'iBeatPulse',
            'iAudioLevel', 'iAudioSpectrum'
        ]

        self.uniform_locs = {}
        for name in uniform_names:
            loc = glGetUniformLocation(self.program, name.encode('ascii'))
            if loc >= 0:
                self.uniform_locs[name] = loc

        # Set resolution
        if 'iResolution' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iResolution'],
                       float(self.width), float(self.height), 1.0)

        # Set mouse to default
        if 'iMouse' in self.uniform_locs:
            glUniform4f(self.uniform_locs['iMouse'], 0.0, 0.0, 0.0, 0.0)

        # Bind texture samplers
        for i in range(4):
            channel_name = f'iChannel{i}'
            if channel_name in self.uniform_locs:
                glUniform1i(self.uniform_locs[channel_name], i)

        # Load textures
        self._load_shader_textures(str(path))

        print(f"Shader loaded: {shader_path}")

    def add_input_source(self, source: InputSource):
        """Add an input source to the renderer."""
        self.input_manager.add_source(source)

    def remove_input_source(self, source: InputSource):
        """Remove an input source from the renderer."""
        self.input_manager.remove_source(source)

    def update_camera(self):
        """Update camera using current camera mode."""
        current_time = time.time()
        dt = current_time - self.camera_mode.last_update_time
        self.camera_mode.last_update_time = current_time

        if dt > 0.1:
            dt = 0.1

        # Get input from keyboard
        keyboard_uniforms = self.keyboard_input.get_uniforms()
        iInput = keyboard_uniforms.get('iInput', (0.0, 0.0, 0.0, 0.0))

        # Convert to camera input format
        input_state = {
            'left': -min(0.0, iInput[0]),
            'right': max(0.0, iInput[0]),
            'up': max(0.0, iInput[1]),
            'down': -min(0.0, iInput[1]),
            'forward': max(0.0, iInput[2]),
            'backward': -min(0.0, iInput[2])
        }

        self.camera_mode.update(input_state, dt, self.shift_pressed)

    def get_camera_vectors(self):
        """Get camera position and orientation vectors."""
        return self.camera_mode.get_vectors()

    def set_camera_mode(self, mode: CameraMode):
        """Switch to a different camera mode."""
        self.camera_mode = mode
        self.camera_mode.last_update_time = time.time()

    def reset_camera(self):
        """Reset camera to default position."""
        self.camera_mode.reset()

    def render(self):
        """Render one frame of the shader."""
        if not self.program:
            raise RuntimeError("No shader loaded. Call load_shader() first.")

        # Update input sources
        elapsed = time.time() - self.start_time
        dt = elapsed - (self.frame_count / 60.0) if self.frame_count > 0 else 0.016
        self.input_manager.update(dt)

        # Update camera
        self.update_camera()

        # Get uniforms from input sources
        input_uniforms = self.input_manager.get_all_uniforms()

        # Update shader uniforms
        glUseProgram(self.program)

        if 'iTime' in self.uniform_locs:
            glUniform1f(self.uniform_locs['iTime'], elapsed)

        if 'iFrame' in self.uniform_locs:
            glUniform1i(self.uniform_locs['iFrame'], self.frame_count)

        if 'iInput' in self.uniform_locs and 'iInput' in input_uniforms:
            glUniform4f(self.uniform_locs['iInput'], *input_uniforms['iInput'])

        # Camera uniforms
        pos, right, up, forward = self.get_camera_vectors()

        if 'iCameraPos' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraPos'], *pos)
        if 'iCameraRight' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraRight'], *right)
        if 'iCameraUp' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraUp'], *up)
        if 'iCameraForward' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraForward'], *forward)

        # Audio uniforms
        for key in ['iBPM', 'iBeatPhase', 'iBeatPulse', 'iAudioLevel']:
            if key in self.uniform_locs:
                value = input_uniforms.get(key, 0.0)
                glUniform1f(self.uniform_locs[key], value)

        if 'iAudioSpectrum' in self.uniform_locs:
            spectrum = input_uniforms.get('iAudioSpectrum', (0.0, 0.0, 0.0, 0.0))
            glUniform4f(self.uniform_locs['iAudioSpectrum'], *spectrum)

        # Bind textures
        for i in range(4):
            if i in self.textures and self.textures[i] is not None:
                glActiveTexture(GL_TEXTURE0 + i)
                glBindTexture(GL_TEXTURE_2D, self.textures[i])

        # Clear and draw
        glClear(GL_COLOR_BUFFER_BIT)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        pos_attrib = glGetAttribLocation(self.program, b"position")
        glEnableVertexAttribArray(pos_attrib)
        glVertexAttribPointer(pos_attrib, 2, GL_FLOAT, GL_FALSE, 0, None)

        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

        glDisableVertexAttribArray(pos_attrib)

        if self.windowed:
            pygame.display.flip()

        self.frame_count += 1

        # Update FPS
        self.fps_frames += 1
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.fps = self.fps_frames / (current_time - self.last_fps_time)
            self.last_fps_time = current_time
            self.fps_frames = 0

    def read_pixels(self) -> np.ndarray:
        """Read rendered pixels from OpenGL framebuffer."""
        pixel_data = glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE)
        frame = np.frombuffer(pixel_data, dtype=np.uint8)
        frame = frame.reshape((self.height, self.width, 3))
        frame = np.flip(frame, axis=0).copy()
        return frame

    def handle_input(self, key: str, pressed: bool):
        """Handle keyboard input."""
        key_map = {
            'up': 'up', 'w': 'up',
            'down': 'down', 's': 'down',
            'left': 'left', 'a': 'left',
            'right': 'right', 'd': 'right',
            'e': 'forward',
            'c': 'backward'
        }

        if key in key_map:
            self.keyboard_input.set_key_state(key_map[key], pressed)

    def handle_events(self) -> bool:
        """
        Handle pygame events (windowed mode only).

        Returns:
            False if quit requested, True otherwise
        """
        if not self.windowed:
            return True

        for event in pygame.event.get():
            if event.type == QUIT:
                return False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE or event.key == K_q:
                    return False
                else:
                    self._handle_keydown(event.key, True)
            elif event.type == KEYUP:
                self._handle_keydown(event.key, False)

        # Update shift state
        keys = pygame.key.get_pressed()
        self.shift_pressed = keys[K_LSHIFT] or keys[K_RSHIFT]

        return True

    def _handle_keydown(self, key, pressed):
        """Handle pygame key events."""
        key_map = {
            K_UP: 'up', K_w: 'w',
            K_DOWN: 'down', K_s: 's',
            K_LEFT: 'left', K_a: 'a',
            K_RIGHT: 'right', K_d: 'd',
            K_e: 'e', K_c: 'c'
        }

        if key in key_map:
            self.handle_input(key_map[key], pressed)

    def get_stats(self) -> dict:
        """Get rendering statistics."""
        elapsed = time.time() - self.start_time
        avg_fps = self.frame_count / elapsed if elapsed > 0 else 0

        return {
            'frames': self.frame_count,
            'elapsed': elapsed,
            'avg_fps': avg_fps,
            'current_fps': self.fps
        }

    def cleanup(self):
        """Clean up resources."""
        self.input_manager.cleanup()

        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()

        if self.context_type == 'egl' and self.egl_display is not None:
            try:
                from OpenGL import EGL

                if self.egl_context is not None:
                    EGL.eglDestroyContext(self.egl_display, self.egl_context)
                if self.egl_surface is not None:
                    EGL.eglDestroySurface(self.egl_display, self.egl_surface)
                EGL.eglTerminate(self.egl_display)

                print("EGL context cleaned up")
            except Exception as e:
                print(f"Warning: Error cleaning up EGL: {e}")

        if self.windowed:
            pygame.quit()

    def __del__(self):
        """Destructor."""
        try:
            self.cleanup()
        except:
            pass
