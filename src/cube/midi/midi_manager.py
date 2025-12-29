"""
MIDI manager for initializing and managing MIDI subsystem.
"""
from typing import Optional
from cube.midi import (
    MIDIState,
    MIDIKeyboardDriver,
    USBMIDIDriver,
    load_midi_config,
)


class MIDIManager:
    """
    Manages MIDI subsystem initialization and state.
    """
    
    def __init__(self, num_channels: int = 7):
        """
        Initialize MIDI manager.
        
        Args:
            num_channels: Number of MIDI channels
        """
        self.midi_state = MIDIState(num_channels=num_channels)
        self.midi_keyboard = MIDIKeyboardDriver(self.midi_state)
        self.midi_config = load_midi_config()
        self.usb_midi: Optional[USBMIDIDriver] = None
        self.last_bpm = None
        
        # Initialize USB MIDI if config available
        if self.midi_config:
            self.usb_midi = USBMIDIDriver(
                self.midi_state, self.midi_config, tap_note=43)
            if self.usb_midi.is_connected():
                print(
                    f'USB MIDI controller connected: {self.usb_midi.connected_device}')
                print('  Tap tempo: Pad 8 (Note 43)')
        else:
            print('No MIDI config found (midi_config.yml) - USB MIDI disabled')
    
    def cleanup(self) -> None:
        """Clean up MIDI resources."""
        if self.usb_midi:
            self.usb_midi.cleanup()

