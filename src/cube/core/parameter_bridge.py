"""
Parameter bridge for cube.

Bridges the old ParameterUniformSource system to the new ParameterRegistry + MappingManager system.
Preserves all existing parameter mapping behavior while enabling DAG-based rendering.
"""
from typing import Dict, Any, Optional
import time
from .parameter import Parameter, ParameterRegistry, ParameterType
from .mapping import Mapping, MappingManager
from .signal import Signal


class MIDISignal(Signal):
    """
    Signal wrapper for MIDI axis values.
    
    Samples the current value of a MIDI axis from InputManager.
    """

    def __init__(self, input_manager, axis):
        """
        Initialize MIDI signal.
        
        Args:
            input_manager: InputManager instance
            axis: Axis enum value (e.g., Axis.PARAM0)
        """
        self.input_manager = input_manager
        self.axis = axis
        self._cached_value = 0.0

    def sample(self, t: float) -> float:
        """
        Sample MIDI axis value.
        
        Returns cached value if axis not present, otherwise returns current value.
        """
        value = self.input_manager.get_axis(self.axis, -1.0)
        if value >= 0.0:
            self._cached_value = value
        return self._cached_value


class KeyboardParamSignal(Signal):
    """
    Signal wrapper for keyboard parameter increment/decrement.
    
    Tracks parameter value changes from keyboard actions.
    """

    def __init__(self, input_manager, param_axis, increment_action, decrement_action):
        """
        Initialize keyboard parameter signal.
        
        Args:
            input_manager: InputManager instance
            param_axis: Axis enum value (e.g., Axis.PARAM0)
            increment_action: Action enum for increment (e.g., Action.INC_PARAM0)
            decrement_action: Action enum for decrement (e.g., Action.DEC_PARAM0)
        """
        self.input_manager = input_manager
        self.param_axis = param_axis
        self.increment_action = increment_action
        self.decrement_action = decrement_action
        self._value = 0.0
        self._last_pressed_actions = set()

    def sample(self, t: float) -> float:
        """
        Sample keyboard parameter value.
        
        Updates value based on pressed actions (increment/decrement).
        """
        pressed_actions = self.input_manager.get_pressed_actions()
        new_actions = pressed_actions - self._last_pressed_actions
        for action in new_actions:
            if action == self.increment_action:
                self._value = max(0.0, min(1.0, self._value + 0.05))
            elif action == self.decrement_action:
                self._value = max(0.0, min(1.0, self._value - 0.05))
        self._last_pressed_actions = pressed_actions.copy()
        return self._value

    def set_value(self, value: float):
        """Set the parameter value directly (used for MIDI override)."""
        self._value = max(0.0, min(1.0, value))


class AudioSignal(Signal):
    """
    Signal wrapper for audio uniform mapping source.
    
    Samples audio signal values from AudioUniformMappingSource.
    """

    def __init__(self, audio_mapping_source, audio_signal_name: str):
        """
        Initialize audio signal.
        
        Args:
            audio_mapping_source: AudioUniformMappingSource instance
            audio_signal_name: Name of audio signal (e.g., "u_audio_rms")
        """
        self.audio_mapping_source = audio_mapping_source
        self.audio_signal_name = audio_signal_name

    def sample(self, t: float) -> float:
        """Sample audio signal value."""
        audio_values = self.audio_mapping_source.get_audio_values()
        return audio_values.get(self.audio_signal_name, 0.0)


class ParameterBridge:
    """
    Bridge between old ParameterUniformSource and new ParameterRegistry + MappingManager.
    
    Maintains compatibility with existing parameter mapping while enabling DAG-based rendering.
    """

    def __init__(self, input_manager, audio_mapping_source=None):
        """
        Initialize parameter bridge.
        
        Args:
            input_manager: InputManager instance
            audio_mapping_source: Optional AudioUniformMappingSource for audio mappings
        """
        self.input_manager = input_manager
        self.audio_mapping_source = audio_mapping_source
        self.registry = ParameterRegistry()
        self.mapping_manager = MappingManager()
        self.param_ids = [f'iParam{i}' for i in range(8)]
        self._create_parameters()
        self._create_mappings()
        self._audio_mapped_params = {param_id: False for param_id in self.param_ids}
        self._update_audio_mappings()

    def _create_parameters(self):
        """Create Parameter objects for iParam0-7."""
        for param_id in self.param_ids:
            param = Parameter(id=param_id, type=ParameterType.FLOAT, value=0.0, min=0.0, max=1.0, default=0.0)
            try:
                self.registry.register(param)
            except ValueError:
                pass

    def _create_mappings(self):
        """Create signal-to-parameter mappings."""
        from cube.input.actions import Axis, Action
        param_actions = {
            Axis.PARAM0: (Action.INC_PARAM0, Action.DEC_PARAM0),
            Axis.PARAM1: (Action.INC_PARAM1, Action.DEC_PARAM1),
            Axis.PARAM2: (Action.INC_PARAM2, Action.DEC_PARAM2),
            Axis.PARAM3: (Action.INC_PARAM3, Action.DEC_PARAM3),
            Axis.PARAM4: (Action.INC_PARAM4, Action.DEC_PARAM4),
            Axis.PARAM5: (Action.INC_PARAM5, Action.DEC_PARAM5),
            Axis.PARAM6: (Action.INC_PARAM6, Action.DEC_PARAM6),
            Axis.PARAM7: (Action.INC_PARAM7, Action.DEC_PARAM7)
        }
        self.keyboard_signals = {}
        for param_axis, (inc_action, dec_action) in param_actions.items():
            param_id = f'iParam{param_axis.name[-1]}'
            keyboard_signal = KeyboardParamSignal(self.input_manager, param_axis, inc_action, dec_action)
            self.keyboard_signals[param_id] = keyboard_signal
            mapping = Mapping(keyboard_signal, param_id)
            self.mapping_manager.add_mapping(mapping)
        
        self.midi_signals = {}
        for param_axis in param_actions.keys():
            param_id = f'iParam{param_axis.name[-1]}'
            midi_signal = MIDISignal(self.input_manager, param_axis)
            self.midi_signals[param_id] = midi_signal

    def _update_audio_mappings(self):
        """Update audio mappings based on AudioUniformMappingSource."""
        if not self.audio_mapping_source:
            return
        audio_mappings = self.audio_mapping_source.get_all_mappings()
        for param_id in self.param_ids:
            audio_signal_name = audio_mappings.get(param_id)
            is_audio_mapped = audio_signal_name is not None
            self._audio_mapped_params[param_id] = is_audio_mapped
            if is_audio_mapped:
                audio_signal = AudioSignal(self.audio_mapping_source, audio_signal_name)
                self._remove_mappings_for_param(param_id)
                mapping = Mapping(audio_signal, param_id)
                self.mapping_manager.add_mapping(mapping)

    def _remove_mappings_for_param(self, param_id: str):
        """Remove all mappings for a parameter."""
        mappings_to_remove = [m for m in self.mapping_manager.all() if m.target_id == param_id]
        for mapping in mappings_to_remove:
            self.mapping_manager.remove_mapping(mapping)

    def update(self, dt: float):
        """
        Update parameter bridge.
        
        This should be called each frame to:
        1. Update audio mapping source
        2. Check for audio mapping changes
        3. Update MIDI values (override keyboard when present)
        4. Update all mappings
        
        Args:
            dt: Delta time since last update
        """
        if self.audio_mapping_source:
            self.audio_mapping_source.update(dt)
            self._update_audio_mappings()
        
        from cube.input.actions import Axis
        for param_id in self.param_ids:
            if self._audio_mapped_params.get(param_id, False):
                continue
            param_num = int(param_id[-1])
            param_axis = getattr(Axis, f'PARAM{param_num}')
            midi_value = self.input_manager.get_axis(param_axis, -1.0)
            if midi_value >= 0.0:
                param = self.registry.get(param_id)
                if param:
                    param.value = midi_value
                    param.clamp()
                    if param_id in self.keyboard_signals:
                        self.keyboard_signals[param_id].set_value(midi_value)
        
        t = time.time()
        self.mapping_manager.update_all(t)

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get current parameter uniforms (for compatibility with old system).
        
        Returns:
            Dictionary with shader uniform values
        """
        uniforms = {}
        if self.audio_mapping_source:
            audio_uniforms = self.audio_mapping_source.get_uniforms()
            uniforms.update(audio_uniforms)
        
        for param_id in self.param_ids:
            if param_id not in uniforms:
                param = self.registry.get(param_id)
                if param:
                    uniforms[param_id] = param.value
        
        from cube.input.actions import Axis
        seed_value = self.input_manager.get_axis(Axis.SEED, 0.0)
        uniforms['iSeed'] = seed_value if seed_value >= 0.0 else 0.0
        
        if 'iBeatPulse' not in uniforms:
            uniforms['iBeatPulse'] = 0.0
        if 'iBeatPhase' not in uniforms:
            uniforms['iBeatPhase'] = 0.0
        
        return uniforms
