"""
Base node class for cube DAG.

All nodes in the DAG inherit from this base class.
"""
from abc import ABC, abstractmethod
from typing import Optional
from ..shader.program import ShaderProgram
from ..render.texture import Texture
from ..core.parameter import ParameterRegistry


class Node(ABC):
    """
    Base class for all nodes in the DAG.
    
    Nodes produce textures by rendering shaders.
    """

    def __init__(self, name: str, shader: Optional[ShaderProgram], width: int, height: int):
        """
        Initialize node.
        
        Args:
            name: Node identifier
            shader: Shader program to use for rendering (None for non-shader nodes)
            width: Output texture width
            height: Output texture height
        """
        self.name = name
        self.shader = shader
        self.enabled = True
        self.output_texture = Texture(width, height)
        self.width = width
        self.height = height
        self._register_parameters()

    def _register_parameters(self):
        """Register node parameters in global registry."""
        if self.shader is None:
            return
        registry = ParameterRegistry()
        for uniform in self.shader.spec.uniforms:
            if uniform.type.value != 'sampler2D':
                param_id = f'{self.name}.{uniform.name}'
                from ..core.parameter import Parameter, ParameterType
                param_type_map = {
                    'float': ParameterType.FLOAT,
                    'vec2': ParameterType.VEC2,
                    'vec3': ParameterType.VEC3,
                    'vec4': ParameterType.VEC4,
                    'bool': ParameterType.BOOL
                }
                param_type = param_type_map.get(uniform.type.value, ParameterType.FLOAT)
                default_value = uniform.default if uniform.default is not None else 0.0
                param = Parameter(
                    id=param_id,
                    type=param_type,
                    value=default_value,
                    min=uniform.min,
                    max=uniform.max,
                    default=uniform.default
                )
                try:
                    registry.register(param)
                except ValueError:
                    pass

    @abstractmethod
    def render(self, t: float, resolution: tuple[float, float]):
        """
        Render the node.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
        """
        pass

    def cleanup(self):
        """Clean up node resources."""
        self.output_texture.cleanup()
