"""
Source node implementation for cube.

SourceNode produces a texture from nothing (no inputs).
"""
from typing import Optional, Dict, Any
from pathlib import Path
from OpenGL.GL import *
from .node import Node
from ..shader.program import ShaderProgram
from ..shader.shader_loader import load_shader_program
from ..utils.gl_utils import draw_fullscreen_quad


class SourceNode(Node):
    """
    Source node that produces a texture from nothing.
    
    Typically used for time-based shaders or base visualizations.
    Loads its own shader program and textures.
    """

    def __init__(self, name: str, shader_path: str, width: int, height: int, vao: int, glsl_version: str = "410"):
        """
        Initialize source node.
        
        Args:
            name: Node identifier
            shader_path: Path to shader file
            width: Output width
            height: Output height
            vao: VAO for fullscreen quad
            glsl_version: GLSL version string
        """
        # Load shader program
        shader_program = load_shader_program(
            shader_path,
            name=name,
            glsl_version=glsl_version,
            vao=vao
        )
        
        super().__init__(name, shader_program, width, height)
        self.vao = vao
        self.shader_path = shader_path
        self._shader_textures: Dict[int, int] = {}
        self._load_shader_textures()
    
    def _load_shader_textures(self):
        """Load textures for this shader based on naming convention."""
        from PIL import Image
        import numpy as np
        
        shader_dir = Path(self.shader_path).parent
        shader_name = Path(self.shader_path).stem
        
        for channel in range(4):
            for ext in ['', '.png', '.jpg', '.jpeg', '.bmp']:
                texture_path = shader_dir / f'{shader_name}.channel{channel}{ext}'
                if texture_path.exists():
                    try:
                        img = Image.open(texture_path).convert('RGB')
                        img_data = np.array(img, dtype=np.uint8)
                        texture_id = glGenTextures(1)
                        glBindTexture(GL_TEXTURE_2D, texture_id)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, img.width, img.height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
                        glBindTexture(GL_TEXTURE_2D, 0)
                        self._shader_textures[channel] = texture_id
                        break
                    except Exception as e:
                        print(f'[SourceNode] Failed to load texture {texture_path}: {e}')
        
        # Create default black texture for iChannel0 if none provided
        if 0 not in self._shader_textures:
            texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            black_pixel = np.zeros((1, 1, 3), dtype=np.uint8)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 1, 1, 0, GL_RGB, GL_UNSIGNED_BYTE, black_pixel)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glBindTexture(GL_TEXTURE_2D, 0)
            self._shader_textures[0] = texture_id

    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None, input_texture_id: Optional[int]=None, shader_textures: Optional[dict]=None):
        """
        Render source node.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
            uniforms: Optional dictionary of uniforms to set (overrides defaults)
            input_texture_id: Optional texture ID to bind to iChannel0 (overrides shader texture)
            shader_textures: Optional dict of {channel: texture_id} (unused, node loads its own)
        """
        if not self.enabled:
            return
        
        self.output_texture.bind()
        # Ensure clear color is black (not white from other contexts)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.shader.use()
        
        # Bind shader textures (iChannel0-3) - use node's own textures
        for channel, texture_id in self._shader_textures.items():
            if texture_id and texture_id > 0:
                channel_name = f'iChannel{channel}'
                self.shader.set_texture(channel_name, channel, texture_id)
        
        # Override iChannel0 if input_texture_id provided
        if input_texture_id is not None and input_texture_id > 0:
            self.shader.set_texture('iChannel0', 0, input_texture_id)
        
        if uniforms:
            for name, value in uniforms.items():
                self.shader.set_uniform(name, value)
        
        draw_fullscreen_quad(self.vao)
        glUseProgram(0)
        self.output_texture.unbind()
    
    def cleanup(self):
        """Clean up shader textures."""
        for tex_id in self._shader_textures.values():
            if tex_id:
                glDeleteTextures([tex_id])
        self._shader_textures.clear()
        super().cleanup()
