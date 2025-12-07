#!/usr/bin/env python3
"""
Test Tap Tempo - Verify BPM detection from pad taps.

Press Pad 8 on your Minilab3 to tap tempo.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cube.midi import MIDIState, USBMIDIDriver, load_midi_config

def main():
    print("=" * 80)
    print("Tap Tempo Test")
    print("=" * 80)
    print()

    # Load config
    config = load_midi_config()
    if not config:
        print("ERROR: No midi_config.yml found!")
        return

    # Create MIDI state
    midi_state = MIDIState(num_channels=4)

    # Create USB MIDI driver with tap tempo (Note 43 = Pad 8)
    usb_midi = USBMIDIDriver(midi_state, config, tap_note=43)
    if not usb_midi.is_connected():
        print("ERROR: USB MIDI not connected!")
        return

    print(f"✓ USB MIDI connected: {usb_midi.connected_device}")
    print(f"✓ Tap tempo enabled: Pad 8 (Note 43)")
    print()

    # Monitor loop
    print("-" * 80)
    print("Tap Pad 8 at a steady tempo (try 120 BPM = 2 taps per second)")
    print("Press Ctrl-C to exit")
    print("-" * 80)
    print()

    last_bpm = None

    try:
        while True:
            # Poll MIDI
            usb_midi.poll()

            # Get BPM
            bpm = usb_midi.tap_tempo.get_bpm()

            if bpm != last_bpm:
                if bpm is not None:
                    beat_duration = usb_midi.tap_tempo.get_beat_duration()
                    num_taps = len(usb_midi.tap_tempo.tap_times)
                    print(f"BPM: {bpm:6.1f}  |  Beat: {beat_duration:.3f}s  |  Taps: {num_taps}")
                else:
                    print("Tempo timeout - tap again to restart")

                last_bpm = bpm

            time.sleep(0.01)  # 100 Hz polling

    except KeyboardInterrupt:
        print("\n" + "-" * 80)
        print("Test stopped")

    finally:
        usb_midi.cleanup()
        print("USB MIDI disconnected")


if __name__ == '__main__':
    main()
