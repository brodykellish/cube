"""
USB MIDI Driver - reads MIDI messages from physical USB MIDI controllers.

Requires python-rtmidi: pip install python-rtmidi
"""

from typing import Optional
import time

try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False
    print("Warning: python-rtmidi not installed. USB MIDI controller support disabled.")
    print("Install with: pip install python-rtmidi")

from .midi_state import MIDIState
from .config_loader import MIDIConfig


class USBMIDIDriver:
    """
    Reads MIDI CC messages from USB MIDI controller and updates MIDIState.

    Supports auto-detection or specific device selection via config.
    """

    def __init__(self, midi_state: MIDIState, config: Optional[MIDIConfig] = None):
        """
        Initialize USB MIDI driver.

        Args:
            midi_state: Shared MIDI state to update
            config: MIDI configuration (device name and CC mappings)
        """
        self.midi_state = midi_state
        self.config = config
        self.midi_in = None
        self.connected_device = None

        if not RTMIDI_AVAILABLE:
            print("USB MIDI driver disabled (python-rtmidi not installed)")
            return

        if config is None:
            print("No MIDI config provided - USB MIDI disabled")
            return

        self._connect()

    def _connect(self):
        """Connect to MIDI device based on config."""
        if not RTMIDI_AVAILABLE:
            return

        try:
            self.midi_in = rtmidi.MidiIn()

            # Get available ports
            available_ports = self.midi_in.get_ports()

            if not available_ports:
                print("No MIDI devices found")
                return

            # Find device
            port_index = None

            if self.config.device_name == "auto":
                # Use first available device
                port_index = 0
                print(f"Auto-selecting MIDI device: {available_ports[0]}")
            else:
                # Find device by name
                for i, port_name in enumerate(available_ports):
                    if self.config.device_name.lower() in port_name.lower():
                        port_index = i
                        print(f"Found MIDI device: {port_name}")
                        break

                if port_index is None:
                    print(f"MIDI device '{self.config.device_name}' not found")
                    print(f"Available devices: {', '.join(available_ports)}")
                    return

            # Open port
            self.midi_in.open_port(port_index)
            self.connected_device = available_ports[port_index]

            # Set callback for incoming messages
            self.midi_in.set_callback(self._midi_callback)

            print(f"USB MIDI connected: {self.connected_device}")
            print(f"Active mappings: {len(self.config.mappings)}")

        except Exception as e:
            print(f"Failed to connect to MIDI device: {e}")
            self.midi_in = None

    def _midi_callback(self, message, data):
        """
        Callback for incoming MIDI messages.

        Args:
            message: Tuple of (message_data, delta_time)
            data: User data (unused)
        """
        midi_message, delta_time = message

        # Parse MIDI message
        # Format: [status_byte, data1, data2]
        if len(midi_message) < 3:
            return

        status = midi_message[0]
        data1 = midi_message[1]  # CC number or note
        data2 = midi_message[2]  # CC value or velocity

        # Check if this is a Control Change message (0xB0-0xBF)
        if (status & 0xF0) == 0xB0:
            cc_number = data1
            cc_value = data2

            # Look up mapping for this CC
            if self.config:
                mapping = self.config.get_mapping_for_cc(cc_number)
                if mapping:
                    # Clamp value to configured range
                    clamped_value = max(mapping.min_val, min(mapping.max_val, cc_value))

                    # Update MIDI state
                    self.midi_state.set_cc(mapping.target_cc, clamped_value)

    def poll(self):
        """
        Poll for MIDI messages (no-op, uses callbacks).

        Call this periodically to keep connection alive.
        """
        # Callbacks handle everything, but we could add connection monitoring here
        pass

    def list_devices(self) -> list:
        """
        List available MIDI input devices.

        Returns:
            List of device name strings
        """
        if not RTMIDI_AVAILABLE or self.midi_in is None:
            return []

        try:
            return self.midi_in.get_ports()
        except Exception:
            return []

    def cleanup(self):
        """Close MIDI connection."""
        if self.midi_in is not None:
            try:
                self.midi_in.close_port()
                print("USB MIDI disconnected")
            except Exception as e:
                print(f"Error closing MIDI port: {e}")
            finally:
                self.midi_in = None
                self.connected_device = None

    def is_connected(self) -> bool:
        """Check if MIDI device is connected."""
        return self.midi_in is not None and self.connected_device is not None
