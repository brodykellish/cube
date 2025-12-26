"""
Signal implementations for parameter control.

Signals wrap various input sources (MIDI, keyboard, audio) to provide
a unified Signal interface for use with SignalParameterHandler.
"""
from cube.core.signal import Signal
from cube.input.input_manager import InputManager
from cube.input.actions import Action, Axis


class MIDISignal(Signal):
    """
    Signal wrapper for MIDI axis values.
    
    Samples the current value of a MIDI axis from InputManager.
    """

    def __init__(self, input_manager: InputManager, axis: Axis):
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

    def __init__(self, input_manager: InputManager, param_axis: Axis, increment_action: Action, decrement_action: Action):
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

