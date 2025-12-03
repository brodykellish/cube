"""
MIDI parameter control system for shader manipulation.

Provides a clean abstraction layer where all shader parameters
are controlled via MIDI CC (Control Change) values, whether from
a real MIDI device or keyboard emulation.
"""

from .midi_state import MIDIState
from .keyboard_driver import MIDIKeyboardDriver
from .uniform_source import MIDIUniformSource

__all__ = [
    'MIDIState',
    'MIDIKeyboardDriver',
    'MIDIUniformSource',
]
