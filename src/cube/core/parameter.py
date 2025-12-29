"""
Parameter system for cube.

Parameters are named, typed, mutable values that can be controlled
by signals through mappings.
"""
from enum import Enum
from typing import Union, Optional, Dict
from dataclasses import dataclass


class ParameterType(Enum):
    """Types of parameters."""
    FLOAT = 'float'
    VEC2 = 'vec2'
    VEC3 = 'vec3'
    VEC4 = 'vec4'
    BOOL = 'bool'


@dataclass
class Parameter:
    """
    A parameter that can be controlled by signals.
    
    Parameters have a globally unique ID, a type, and constraints.
    """
    id: str
    type: ParameterType
    value: Union[float, tuple, bool]
    min: Optional[float] = None
    max: Optional[float] = None
    default: Optional[Union[float, tuple, bool]] = None

    def __post_init__(self):
        """Set default value if not provided."""
        if self.default is None:
            self.default = self.value

    def reset(self):
        """Reset parameter to default value."""
        self.value = self.default

    def clamp(self):
        """Clamp value to min/max if applicable."""
        if self.type == ParameterType.FLOAT and self.min is not None and self.max is not None:
            self.value = max(self.min, min(self.max, self.value))

