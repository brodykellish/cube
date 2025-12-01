"""
Base shader renderer with shared functionality.

This module contains the base class that is extended by platform-specific
implementations (pygame for MacOS, EGL for Raspberry Pi).
"""

import time
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from abc import ABC, abstractmethod

from OpenGL.GL import *
from OpenGL.GL import shaders

from .camera_modes import CameraMode, SphericalCamera
from .input_sources import InputManager, KeyboardInput, InputSource


class ShaderRendererBase(ABC):
    """
    Base shader renderer with shared functionality.
    
    Platform-specific implementations should inherit from this class
    and implement the abstract methods for context creation.
    """
    
    def __init__(self, width: int, height: int, scale: int = 1):
        """
        Initialize base shader renderer.
        
        Args:
            width: Render width in pixels
            height: Render height in pixels
            scale: Window scale factor (platform-specific usage)
        """
        self.width = width
        self.height = height
        self.scale = scale
        self.start_time = time.time()
        self.frame_count = 0
        self.last_fps_time = self.start_time
        self.fps = 0.0
        self.fps_frames = 0
        
        self.input_manager = InputManager()
        self.keyboard_input = KeyboardInput()
        self.input_manager.add_source(self.keyboard_input)
        
        self.camera_mode = SphericalCamera(
            distance=12.0,
            yaw=0.785,
            pitch=0.6,
            rotate_speed=1.5,
            zoom_speed=5.0,
            damping=0.9
        )
        
        self.shift_pressed = False
        
        self.program = None
        self.vbo = None
        self.uniform_locs = {}
        self.textures = {}
        
        self._init_context()
        
        glViewport(0, 0, self._get_viewport_width(), self._get_viewport_height())
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_DITHER)
        
        self._create_fullscreen_quad()
    
    @abstractmethod
    def _init_context(self):
        """Initialize OpenGL context (platform-specific)."""
        pass
    
    @abstractmethod
    def _get_viewport_width(self) -> int:
        """Get viewport width (platform-specific)."""
        pass
    
    @abstractmethod
    def _get_viewport_height(self) -> int:
        """Get viewport height (platform-specific)."""
        pass
    
    @abstractmethod
    def _swap_buffers(self):
        """Swap buffers / present frame (platform-specific)."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up platform-specific resources."""
        pass
    
    def handle_events(self) -> bool:
        """
        Handle platform-specific events (optional, for window lifecycle).
        
        Base implementation always returns True. Override in windowed implementations
        to handle quit events.
        
        Returns:
            False if quit requested, True otherwise
        """
        return True
    
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
    
    def _load_texture(self, image_path: str) -> Optional[int]:
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
        for tex_id in self.textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.textures.clear()
        
        shader_dir = Path(shader_path).parent
        shader_name = Path(shader_path).stem
        
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
        
        vertex_source = """#version 100
attribute vec2 position;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}
"""

        fragment_wrapped = f"""#version 100
precision mediump float;
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
        
        try:
            vertex_shader = shaders.compileShader(vertex_source, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(fragment_wrapped, GL_FRAGMENT_SHADER)
            self.program = shaders.compileProgram(vertex_shader, fragment_shader)
        except RuntimeError as e:
            raise RuntimeError(f"Shader compilation failed: {e}")
        
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
        
        if 'iResolution' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iResolution'],
                       float(self.width), float(self.height), 1.0)
        
        if 'iMouse' in self.uniform_locs:
            glUniform4f(self.uniform_locs['iMouse'], 0.0, 0.0, 0.0, 0.0)
        
        for i in range(4):
            channel_name = f'iChannel{i}'
            if channel_name in self.uniform_locs:
                glUniform1i(self.uniform_locs[channel_name], i)
        
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
        
        keyboard_uniforms = self.keyboard_input.get_uniforms()
        iInput = keyboard_uniforms.get('iInput', (0.0, 0.0, 0.0, 0.0))
        
        input_state = {
            'left': -min(0.0, iInput[0]),
            'right': max(0.0, iInput[0]),
            'up': max(0.0, iInput[1]),
            'down': -min(0.0, iInput[1]),
            'forward': max(0.0, iInput[2]),
            'backward': -min(0.0, iInput[2])
        }
        
        self.camera_mode.update(input_state, dt, self.shift_pressed)
    
    def get_camera_vectors(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
        
        elapsed = time.time() - self.start_time
        dt = elapsed - (self.frame_count / 60.0) if self.frame_count > 0 else 0.016
        self.input_manager.update(dt)
        
        self.update_camera()
        
        input_uniforms = self.input_manager.get_all_uniforms()
        
        glUseProgram(self.program)
        
        if 'iTime' in self.uniform_locs:
            glUniform1f(self.uniform_locs['iTime'], elapsed)
        
        if 'iFrame' in self.uniform_locs:
            glUniform1i(self.uniform_locs['iFrame'], self.frame_count)
        
        if 'iInput' in self.uniform_locs and 'iInput' in input_uniforms:
            glUniform4f(self.uniform_locs['iInput'], *input_uniforms['iInput'])
        
        pos, right, up, forward = self.get_camera_vectors()
        
        if 'iCameraPos' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraPos'], *pos)
        if 'iCameraRight' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraRight'], *right)
        if 'iCameraUp' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraUp'], *up)
        if 'iCameraForward' in self.uniform_locs:
            glUniform3f(self.uniform_locs['iCameraForward'], *forward)
        
        for key in ['iBPM', 'iBeatPhase', 'iBeatPulse', 'iAudioLevel']:
            if key in self.uniform_locs:
                value = input_uniforms.get(key, 0.0)
                glUniform1f(self.uniform_locs[key], value)
        
        if 'iAudioSpectrum' in self.uniform_locs:
            spectrum = input_uniforms.get('iAudioSpectrum', (0.0, 0.0, 0.0, 0.0))
            glUniform4f(self.uniform_locs['iAudioSpectrum'], *spectrum)
        
        for i in range(4):
            if i in self.textures and self.textures[i] is not None:
                glActiveTexture(GL_TEXTURE0 + i)
                glBindTexture(GL_TEXTURE_2D, self.textures[i])
        
        glClear(GL_COLOR_BUFFER_BIT)
        
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        pos_attrib = glGetAttribLocation(self.program, b"position")
        glEnableVertexAttribArray(pos_attrib)
        glVertexAttribPointer(pos_attrib, 2, GL_FLOAT, GL_FALSE, 0, None)
        
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        
        glDisableVertexAttribArray(pos_attrib)
        
        self._swap_buffers()
        
        self.frame_count += 1
        
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
    
    def __del__(self):
        """Destructor."""
        try:
            self.cleanup()
        except:
            pass

