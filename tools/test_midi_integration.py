#!/usr/bin/env python3
"""
Test MIDI Integration - Verifies USB MIDI → MIDIState flow.

This script tests if MIDI messages from your controller are:
1. Being received by the USB MIDI driver
2. Correctly mapped by the config
3. Updating the MIDI state
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cube.midi import MIDIState, USBMIDIDriver, load_midi_config

def main():
    print("=" * 80)
    print("MIDI Integration Test")
    print("=" * 80)
    print()

    # Load config
    config = load_midi_config()
    if not config:
        print("ERROR: No midi_config.yml found!")
        print("Please create midi_config.yml in the project root.")
        return

    print(f"✓ Config loaded: {config.device_name}")
    print(f"  Mappings:")
    for mapping in config.mappings:
        print(f"    CC#{mapping.midi_cc} → {mapping.target} (CC#{mapping.target_cc})")
    print()

    # Create MIDI state
    midi_state = MIDIState(num_channels=4)
    print(f"✓ MIDI State created")
    print(f"  Initial values: {midi_state}")
    print()

    # Create USB MIDI driver
    usb_midi = USBMIDIDriver(midi_state, config)
    if not usb_midi.is_connected():
        print("ERROR: USB MIDI not connected!")
        print("Available devices:")
        for device in usb_midi.list_devices():
            print(f"  - {device}")
        return

    print(f"✓ USB MIDI connected: {usb_midi.connected_device}")
    print()

    # Monitor loop
    print("-" * 80)
    print("Monitoring MIDI parameters (move your faders/knobs):")
    print("  param0 (CC0) = mapped from CC 74")
    print("  param1 (CC1) = mapped from CC 71")
    print("  param2 (CC2) = mapped from CC 76")
    print("  param3 (CC3) = mapped from CC 77")
    print()
    print("Press Ctrl-C to exit")
    print("-" * 80)
    print()

    last_values = [None, None, None, None]

    try:
        while True:
            # Poll MIDI (callbacks do the work, but keep connection alive)
            usb_midi.poll()

            # Check for changes
            current_values = [
                midi_state.get_cc(0),
                midi_state.get_cc(1),
                midi_state.get_cc(2),
                midi_state.get_cc(3),
            ]

            # Print changes
            for i, (last, current) in enumerate(zip(last_values, current_values)):
                if last != current:
                    normalized = midi_state.get_normalized(i)
                    print(f"param{i} (CC{i}): {current:3d} / 127 = {normalized:.3f}")

            last_values = current_values
            time.sleep(0.01)  # 100 Hz polling

    except KeyboardInterrupt:
        print("\n" + "-" * 80)
        print("Test stopped")
        print()
        print(f"Final MIDI state: {midi_state}")

    finally:
        usb_midi.cleanup()
        print("USB MIDI disconnected")


if __name__ == '__main__':
    main()
