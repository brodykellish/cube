"""
MIDI input source - provides MIDI input as actions and axes.

Wraps MIDIState to provide:
- MIDI notes as discrete actions (pads, keys)
- MIDI CCs as continuous axes (knobs, faders)
- Chord seed calculation from active notes
"""
from typing import Dict
from .input_source import InputSource, InputState

class MIDIInputSource(InputSource):
    """
    MIDI input source - reads from centralized MIDIState.

    Provides:
    - MIDI notes as discrete actions (pads, keys) - format: 'midi:note_X'
    - MIDI CCs as continuous axes (knobs, faders) - format: 'midi:cc_X'
    - Chord seed calculation from active notes

    Outputs uniform key format for notes.
    Modifiers (shift, CC 9) are handled by InputManager.
    """

    def __init__(self, midi_state, priority: int=100):
        """
        Initialize MIDI input source.

        Args:
            midi_state: MIDIState instance (central MIDI state)
            priority: Priority for conflict resolution (default: 100)
        """
        self.midi_state = midi_state
        self._priority = priority
        self._last_notes = set()
        self._last_cc = {}

    @property
    def name(self) -> str:
        """Source name"""
        return 'midi'

    @property
    def priority(self) -> int:
        """Priority for conflict resolution"""
        return self._priority

    def poll(self) -> InputState:
        """
        Poll MIDI state and return InputState.

        Returns uniform key format: 'midi:note_X' for notes, 'midi:cc_X' for axes.

        Returns:
            InputState with MIDI notes and CCs
        """
        # Current MIDIState implementation tracks only CC values (no notes),
        # so we expose CCs as axes and leave pressed/released/held empty.
        pressed = set()
        released = set()
        held = set()
        
        axes: Dict[str, float] = {}
        cc_values = self.midi_state.get_cc_values()
        for cc, _ in cc_values.items():
            value = self.midi_state.get_normalized(cc)
            axes[f'midi:cc_{cc}'] = value
            self._last_cc[cc] = value
        
        return InputState(
            source_name=self.name,
            source_priority=self.priority,
            pressed=pressed,
            released=released,
            held=held,
            axes=axes,
            quit_requested=False,
            paste_text=None
        )

    def is_available(self) -> bool:
        """
        Check if MIDI is available.

        Returns:
            True always (MIDIState is always available)
        """
        return True

    def cleanup(self):
        """Clean up MIDI resources (no-op, managed by USBMIDIDriver)"""
        pass