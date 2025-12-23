"""
Factory for creating EffectNode instances.

Allows storing effect configuration as instances while deferring
actual EffectNode creation until runtime when all dependencies are available.
"""
from typing import Callable, Optional
from .effect_node import EffectNode


class EffectNodeFactory:
    """
    Factory that creates EffectNode instances on demand.
    
    Stores effect configuration and can create instances when provided
    with runtime dependencies (shader, texture, dimensions, VAO).
    """

    def __init__(self, effect_node_class: type, shader_path: str):
        """
        Initialize factory.
        
        Args:
            effect_node_class: EffectNode class (or subclass) to instantiate
            shader_path: Path to effect shader file
        """
        self.effect_node_class = effect_node_class
        self.shader_path = shader_path

    def create(self, name: str, shader, input_texture, width: int, height: int, vao: int) -> EffectNode:
        """
        Create an EffectNode instance.
        
        Args:
            name: Node identifier
            shader: Shader program (already loaded)
            input_texture: Input texture to process
            width: Output width
            height: Output height
            vao: VAO for fullscreen quad
            
        Returns:
            New EffectNode instance
        """
        return self.effect_node_class(name, shader, input_texture, width, height, vao)

    def __call__(self, name: str, shader, input_texture, width: int, height: int, vao: int) -> EffectNode:
        """Allow factory to be called directly."""
        return self.create(name, shader, input_texture, width, height, vao)
