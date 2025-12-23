# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/spec.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-22 16:49:42 UTC (1766422182)

"""
Shader specification system for cube.

ShaderSpec defines the interface of a shader (uniforms, inputs, outputs)
without the actual GLSL code.
"""
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class UniformType(Enum):
    """Types of uniform parameters."""
    FLOAT = 'float'
    VEC2 = 'vec2'
    VEC3 = 'vec3'
    VEC4 = 'vec4'
    BOOL = 'bool'
    SAMPLER2D = 'sampler2D'

@dataclass
class UniformSpec:
    """
    Specification for a single uniform parameter.
    
    Defines the name, type, and constraints for a uniform.
    """
    name: str
    type: UniformType
    min: Optional[float] = None
    max: Optional[float] = None
    default: Optional[float] = None

@dataclass
class ShaderSpec:
    """
    Specification for a shader program.
    
    Defines the interface (uniforms, inputs, outputs) without
    the actual GLSL source code.
    """
    name: str
    uniforms: List[UniformSpec]
    inputs: int = 0
    outputs: int = 1

    def __post_init__(self):
        """Validate specification."""
        if self.inputs < 0:
            raise ValueError('inputs must be >= 0')
        if self.outputs != 1:
            raise ValueError('outputs must be 1 (only single output supported)')