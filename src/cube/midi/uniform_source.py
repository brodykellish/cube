"""
MIDI Uniform Source - converts MIDI CC values to shader uniforms.

Implements the UniformSource interface, making MIDI parameters
available to shaders just like keyboard, audio, etc.
"""

from typing import Dict, Any
from cube.shader.uniform_sources import UniformSource
from .midi_state import MIDIState


class MIDIUniformSource(UniformSource):
    """
    Provides shader uniforms from MIDI CC values.

    Uniforms provided:
    - iParam0 (float): Normalized CC0 value (0.0-1.0)
    - iParam1 (float): Normalized CC1 value (0.0-1.0)
    - iParam2 (float): Normalized CC2 value (0.0-1.0)
    - iParam3 (float): Normalized CC3 value (0.0-1.0)
    - iParams (vec4): All params as a vector (param0, param1, param2, param3)

    Example shader usage:
        uniform float iParam0;  // Individual access
        uniform vec4 iParams;   // Vector access

        void mainImage(out vec4 fragColor, in vec2 fragCoord) {
            float radius = mix(0.5, 5.0, iParam0);  // CC0 controls radius
            vec3 color = vec3(iParam1, iParam2, iParam3);  // CC1-3 control RGB
            // ...
        }
    """

    def __init__(self, midi_state: MIDIState):
        """
        Initialize MIDI uniform source.

        Args:
            midi_state: Shared MIDI state (updated by keyboard/USB MIDI)
        """
        self.midi_state = midi_state

    def update(self, dt: float):
        """
        Update MIDI uniforms (no-op, state is updated externally).

        Args:
            dt: Delta time (unused)
        """
        pass

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get current MIDI parameter values as shader uniforms.

        Returns:
            Dictionary with iParam0-3 (floats) and iParams (vec4 tuple)
        """
        # Get normalized values (0.0-1.0)
        param0 = self.midi_state.get_normalized(0)
        param1 = self.midi_state.get_normalized(1)
        param2 = self.midi_state.get_normalized(2)
        param3 = self.midi_state.get_normalized(3)

        return {
            'iParam0': param0,
            'iParam1': param1,
            'iParam2': param2,
            'iParam3': param3,
            'iParams': (param0, param1, param2, param3),
        }

    def cleanup(self):
        """No cleanup needed for MIDI uniform source."""
        pass

    def reset(self):
        """Reset MIDI state to defaults."""
        self.midi_state.reset()
