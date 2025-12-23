"""
Mapping system for cube.

Mappings connect signals to parameters, allowing signals to control
parameter values.
"""
from typing import Callable, Optional, List, Union
from .signal import Signal
from .parameter import Parameter, ParameterRegistry


class Mapping:
    """
    Maps a signal to a parameter with optional transformation.
    
    A mapping samples a signal and updates a parameter value.
    """
    pass

    def __init__(self, source: Signal, target: Union[Parameter, str], transform: Optional[Callable[[float], float]]=None):
        """
        Initialize mapping.
        
        Args:
            source: Signal to sample
            target: Target parameter (Parameter object or ID string)
            transform: Optional function to transform signal value
        """
        self.source = source
        if isinstance(target, Parameter):
            self._target_param = target
            self._target_id = target.id
        else:
            self._target_param = None
            self._target_id = target
        self.transform = transform or (lambda x: x)

    @property
    def target(self) -> Optional[Parameter]:
        """Get target parameter."""
        if self._target_param is None:
            registry = ParameterRegistry()
            self._target_param = registry.get(self._target_id)
        return self._target_param

    @property
    def target_id(self) -> str:
        """Get target parameter ID."""
        return self._target_id

    def apply(self, t: float):
        """
        Sample signal and update target parameter.
        
        Args:
            t: Current time in seconds
        """
        param = self.target
        if param is None:
            print(f"[Mapping] Target parameter '{self._target_id}' not found")
            return
        signal_value = self.source.sample(t)
        transformed_value = self.transform(signal_value)
        old_value = param.value
        
        if param.type.value == 'float':
            param.value = transformed_value
            param.clamp()
        elif param.type.value == 'bool':
            param.value = transformed_value > 0.5
        else:
            param.value = transformed_value
        
        if old_value != param.value:
            print(f'[Mapping] Updated {self._target_id}: {old_value} -> {param.value} (signal={signal_value}, transformed={transformed_value})')


class MappingManager:
    """
    Manages all signal-to-parameter mappings.
    
    Provides a central place to register and update mappings.
    """

    def __init__(self):
        """Initialize mapping manager."""
        self._mappings = []

    def add_mapping(self, mapping: Mapping):
        """Add a mapping."""
        self._mappings.append(mapping)

    def remove_mapping(self, mapping: Mapping):
        """Remove a mapping."""
        if mapping in self._mappings:
            self._mappings.remove(mapping)

    def update_all(self, t: float):
        """
        Update all mappings at time t.
        
        Args:
            t: Current time in seconds
        """
        for mapping in self._mappings:
            mapping.apply(t)

    def clear(self):
        """Clear all mappings."""
        self._mappings.clear()

    def all(self) -> List[Mapping]:
        """Get all mappings."""
        return self._mappings.copy()
