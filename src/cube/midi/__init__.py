"""
MIDI parameter control system for shader manipulation.

Provides a clean abstraction layer where all shader parameters
are controlled via MIDI CC (Control Change) values, whether from
a real MIDI device or keyboard emulation.
"""

from .midi_state import MIDIState
from .keyboard_driver import MIDIKeyboardDriver
from .usb_driver import USBMIDIDriver
from .config_loader import load_midi_config, MIDIConfig, MIDIMapping
from .tap_tempo import TapTempoDetector

__all__ = [
    'MIDIState',
    'MIDIKeyboardDriver',
    'USBMIDIDriver',
    'load_midi_config',
    'MIDIConfig',
    'MIDIMapping',
    'TapTempoDetector',
]
