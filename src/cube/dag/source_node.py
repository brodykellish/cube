"""
Source node implementation for cube.

SourceNode produces a texture from nothing (no inputs).
"""
from typing import Optional, Dict, Any
from OpenGL.GL import *
from .node import Node
from ..shader.program import ShaderProgram
from ..utils.gl_utils import draw_fullscreen_quad


class SourceNode(Node):
    """
    Source node that produces a texture from nothing.
    
    Typically used for time-based shaders or base visualizations.
    """

    def __init__(self, name: str, shader: ShaderProgram, width: int, height: int, vao: int):
        """
        Initialize source node.
        
        Args:
            name: Node identifier
            shader: Shader program
            width: Output width
            height: Output height
            vao: VAO for fullscreen quad
        """
        super().__init__(name, shader, width, height)
        self.vao = vao

    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None, input_texture_id: Optional[int]=None, shader_textures: Optional[dict]=None):
        """
        Render source node.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
            uniforms: Optional dictionary of uniforms to set (overrides defaults)
            input_texture_id: Optional texture ID to bind to iChannel0
            shader_textures: Optional dict of {channel: texture_id} for iChannel0-3
        """
        if not self.enabled:
            return
        
        self.output_texture.bind()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.shader.use()
        
        # Bind shader textures (iChannel0-3)
        if shader_textures:
            for channel, texture_id in shader_textures.items():
                if texture_id and texture_id > 0:
                    channel_name = f'iChannel{channel}'
                    self.shader.set_texture(channel_name, channel, texture_id)
        
        if input_texture_id is not None and input_texture_id > 0:
            self.shader.set_texture('iChannel0', 0, input_texture_id)
        
        if uniforms:
            for name, value in uniforms.items():
                self.shader.set_uniform(name, value)
        
        draw_fullscreen_quad(self.vao)
        glUseProgram(0)
        self.output_texture.unbind()
