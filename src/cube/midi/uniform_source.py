"""
MIDI Uniform Source - converts MIDI CC values to shader uniforms.

Implements the UniformSource interface, making MIDI parameters
available to shaders just like keyboard, audio, etc.
"""

from typing import Dict, Any, Optional
from cube.shader.uniform_sources import UniformSource
from .midi_state import MIDIState
from .tap_tempo import TapTempoDetector


class MIDIUniformSource(UniformSource):
    """
    Provides shader uniforms from MIDI CC values.

    Uniforms provided:
    - iParam0 (float): Normalized CC0 value (0.0-1.0)
    - iParam1 (float): Normalized CC1 value (0.0-1.0)
    - iParam2 (float): Normalized CC2 value (0.0-1.0)
    - iParam3 (float): Normalized CC3 value (0.0-1.0)
    - iParams (vec4): All params as a vector (param0, param1, param2, param3)
    - iBPM (float): Detected BPM from tap tempo (0.0 if no tempo detected)
    - iBeat (float): Beat duration in seconds (0.0 if no tempo)

    Example shader usage:
        uniform float iParam0;  // Individual access
        uniform vec4 iParams;   // Vector access
        uniform float iBPM;     // Tap tempo BPM
        uniform float iBeat;    // Beat duration in seconds

        void mainImage(out vec4 fragColor, in vec2 fragCoord) {
            float radius = mix(0.5, 5.0, iParam0);  // CC0 controls radius
            vec3 color = vec3(iParam1, iParam2, iParam3);  // CC1-3 control RGB

            // Pulse with the beat
            float pulse = sin(iTime / iBeat * 6.28318);  // Sine wave synced to BPM
            // ...
        }
    """

    def __init__(self, midi_state: MIDIState, tap_tempo: Optional[TapTempoDetector] = None):
        """
        Initialize MIDI uniform source.

        Args:
            midi_state: Shared MIDI state (updated by keyboard/USB MIDI)
            tap_tempo: Optional tap tempo detector for BPM tracking
        """
        self.midi_state = midi_state
        self.tap_tempo = tap_tempo

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
            Dictionary with iParam0-3 (floats), iParams (vec4 tuple), and iBeatTrigger
        """
        # Get normalized values (0.0-1.0)
        param0 = self.midi_state.get_normalized(0)
        param1 = self.midi_state.get_normalized(1)
        param2 = self.midi_state.get_normalized(2)
        param3 = self.midi_state.get_normalized(3)

        # Get beat trigger from tap tempo (if available)
        beat_trigger = 0.0
        bpm = 0.0
        if self.tap_tempo:
            # Update envelope parameters from MIDI state (CC 4, 5, 6)
            # Map 0-127 MIDI values to reasonable time ranges with minimums
            # Use mix() pattern: min + (max - min) * normalized
            attack = 0.02 + (0.3 - 0.02) * self.midi_state.get_normalized(4)  # 20-300ms
            hold = 0.05 + (0.4 - 0.05) * self.midi_state.get_normalized(5)    # 50-400ms
            decay = 0.1 + (0.8 - 0.1) * self.midi_state.get_normalized(6)     # 100-800ms

            self.tap_tempo.set_envelope(attack, hold, decay)
            beat_trigger = self.tap_tempo.get_beat_trigger()

            # Get BPM for debug display
            detected_bpm = self.tap_tempo.get_bpm()
            if detected_bpm is not None:
                bpm = detected_bpm

        return {
            'iParam0': param0,
            'iParam1': param1,
            'iParam2': param2,
            'iParam3': param3,
            'iParams': (param0, param1, param2, param3),
            'iBeatTrigger': beat_trigger,
            'iBPM': bpm,  # For debug display
        }

    def cleanup(self):
        """No cleanup needed for MIDI uniform source."""
        pass

    def reset(self):
        """Reset MIDI state to defaults."""
        self.midi_state.reset()
