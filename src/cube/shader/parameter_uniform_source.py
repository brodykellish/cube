# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/parameter_uniform_source.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-23 00:23:29 UTC (1766449409)

"""
Parameter uniform source for shader parameters.

Handles both MIDI (direct mapping) and keyboard (increment/decrement) control.
Uses reverse index for efficient O(active_actions) dispatch.

Audio mappings override MIDI/keyboard when bound.
"""
from typing import Dict, Any
from cube.shader.uniform_sources import UniformSource
from cube.input.actions import Axis, Action

class ParameterUniformSource(UniformSource):
    """
    Provides shader parameter uniforms from InputManager.

    Uniforms provided:
    - iParam0-7: General shader parameters (0.0-1.0)
    - iSeed: Random seed from MIDI chord (0.0-1.0)
    - iBeatPulse: Beat pulse (0.0-1.0)
    - iBeatPhase: Beat phase (0.0-1.0)

    Priority order:
    1. Audio mapping (if bound via AudioUniformMappingSource)
    2. MIDI knobs: Direct mapping (CC value → parameter)
    3. Keyboard: Increment/decrement (n/m, ,/., etc.)

    Caches values to persist when inputs stop.
    """

    def __init__(self, input_manager, audio_mapping_source=None):
        """
        Initialize parameter uniform source.

        Args:
            input_manager: InputManager instance to pull from
            audio_mapping_source: Optional AudioUniformMappingSource for audio overrides
        """
        self.input_manager = input_manager
        self.audio_mapping_source = audio_mapping_source

        # Cached parameter values (persist when inputs stop).
        self._cached_params = {
            Axis.PARAM0: 0.0,
            Axis.PARAM1: 0.0,
            Axis.PARAM2: 0.0,
            Axis.PARAM3: 0.0,
            Axis.PARAM4: 0.0,
            Axis.PARAM5: 0.0,
            Axis.PARAM6: 0.0,
            Axis.PARAM7: 0.0,
            Axis.SEED: 0.0,
        }

        # Keyboard actions for incrementing/decrementing parameters.
        # Positive deltas are "INC_*", negative deltas are "DEC_*".
        self._param_actions = {
            Action.INC_PARAM0: (Axis.PARAM0, 0.05),
            Action.DEC_PARAM0: (Axis.PARAM0, -0.05),
            Action.INC_PARAM1: (Axis.PARAM1, 0.05),
            Action.DEC_PARAM1: (Axis.PARAM1, -0.05),
            Action.INC_PARAM2: (Axis.PARAM2, 0.05),
            Action.DEC_PARAM2: (Axis.PARAM2, -0.05),
            Action.INC_PARAM3: (Axis.PARAM3, 0.05),
            Action.DEC_PARAM3: (Axis.PARAM3, -0.05),
            Action.INC_PARAM4: (Axis.PARAM4, 0.05),
            Action.DEC_PARAM4: (Axis.PARAM4, -0.05),
            Action.INC_PARAM5: (Axis.PARAM5, 0.05),
            Action.DEC_PARAM5: (Axis.PARAM5, -0.05),
            Action.INC_PARAM6: (Axis.PARAM6, 0.05),
            Action.DEC_PARAM6: (Axis.PARAM6, -0.05),
            Action.INC_PARAM7: (Axis.PARAM7, 0.05),
            Action.DEC_PARAM7: (Axis.PARAM7, -0.05),
        }

    def update(self, dt: float):
        """
        Update cached parameter values from InputManager.

        Handles both MIDI (direct mapping) and keyboard (increment/decrement).

        Args:
            dt: Delta time since last update
        """
        if self.audio_mapping_source:
            self.audio_mapping_source.update(dt)

        # Apply discrete increments from pressed and held actions.
        # Held actions apply a smaller delta scaled by dt for smooth adjustment.
        def apply_action_delta(action_set, scale: float = 1.0):
            for action in action_set:
                if action in self._param_actions:
                    param_axis, delta = self._param_actions[action]
                    old_value = self._cached_params[param_axis]
                    new_value = max(0.0, min(1.0, old_value + delta * scale))
                    self._cached_params[param_axis] = new_value

        apply_action_delta(self.input_manager.get_pressed_actions(), scale=1.0)
        apply_action_delta(self.input_manager.get_held_actions(), scale=dt * 4.0)  # gentle continuous adjustment

        # Direct axis overrides (e.g., MIDI CC mapped to PARAM axes)
        for param_axis in [
            Axis.PARAM0,
            Axis.PARAM1,
            Axis.PARAM2,
            Axis.PARAM3,
            Axis.PARAM4,
            Axis.PARAM5,
            Axis.PARAM6,
            Axis.PARAM7,
            Axis.SEED,
        ]:
            value = self.input_manager.get_axis(param_axis, -1.0)
            if value > -1.0:
                self._cached_params[param_axis] = value

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get current parameter uniforms.

        Audio mappings override MIDI/keyboard when bound.
        Returns cached values for unbound parameters (persist even when MIDI stops reporting).

        Returns:
            Dictionary with shader uniform values
        """
        uniforms = {}
        if self.audio_mapping_source:
            audio_uniforms = self.audio_mapping_source.get_uniforms()
            uniforms.update(audio_uniforms)

            # Propagate audio-driven params into cached Axis-keyed values
            for param_name, param_axis in {
                'iParam0': Axis.PARAM0,
                'iParam1': Axis.PARAM1,
                'iParam2': Axis.PARAM2,
                'iParam3': Axis.PARAM3,
                'iParam4': Axis.PARAM4,
                'iParam5': Axis.PARAM5,
                'iParam6': Axis.PARAM6,
                'iParam7': Axis.PARAM7,
            }.items():
                if param_name in audio_uniforms:
                    self._cached_params[param_axis] = audio_uniforms[param_name]

        param_mappings = {
            'iParam0': Axis.PARAM0, 
            'iParam1': Axis.PARAM1,
            'iParam2': Axis.PARAM2,
            'iParam3': Axis.PARAM3,
            'iParam4': Axis.PARAM4,
            'iParam5': Axis.PARAM5,
            'iParam6': Axis.PARAM6,
            'iParam7': Axis.PARAM7,
        }
        for param_name, param_axis in param_mappings.items():
            if param_name not in uniforms:
                uniforms[param_name] = self._cached_params[param_axis]
        uniforms['iSeed'] = self._cached_params[Axis.SEED]
        if 'iBeatPulse' not in uniforms:
            uniforms['iBeatPulse'] = 0.0
        if 'iBeatPhase' not in uniforms:
            uniforms['iBeatPhase'] = 0.0
        return uniforms

    def get_param_values(self) -> list[float]:
        """Return cached parameter values in index order for debug/telemetry."""
        return [
            self._cached_params[Axis.PARAM0],
            self._cached_params[Axis.PARAM1],
            self._cached_params[Axis.PARAM2],
            self._cached_params[Axis.PARAM3],
            self._cached_params[Axis.PARAM4],
            self._cached_params[Axis.PARAM5],
            self._cached_params[Axis.PARAM6],
            self._cached_params[Axis.PARAM7],
        ]

    def cleanup(self):
        """Clean up resources."""
        if self.audio_mapping_source:
            try:
                self.audio_mapping_source.cleanup()
            except Exception:
                pass
        return