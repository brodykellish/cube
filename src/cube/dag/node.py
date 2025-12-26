"""
Base node class for cube DAG.

All nodes in the DAG inherit from this base class.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from ..shader.program import ShaderProgram
from ..render.texture import Texture


class Node(ABC):
    """
    Base class for all nodes in the DAG.
    
    Nodes produce textures by rendering shaders.
    Nodes track their own connections (doubly-linked structure).
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
        
        # Connection tracking (doubly-linked)
        self.parent: Optional['Node'] = None  # Node that feeds into this one
        self.children: List['Node'] = []  # Nodes that this node feeds into

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
