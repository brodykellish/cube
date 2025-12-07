#!/usr/bin/env python3
"""
Test Beat Trigger - Verify beat trigger with ADSR envelope.

Press Pad 8 to tap tempo, turn knobs 6-8 to adjust envelope.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cube.midi import MIDIState, USBMIDIDriver, load_midi_config

def draw_trigger_bar(value: float, width: int = 40) -> str:
    """Draw a horizontal bar showing trigger value."""
    filled = int(value * width)
    bar = '█' * filled + '░' * (width - filled)
    return bar

def main():
    print("=" * 80)
    print("Beat Trigger Test - ADSR Envelope")
    print("=" * 80)
    print()

    # Load config
    config = load_midi_config()
    if not config:
        print("ERROR: No midi_config.yml found!")
        return

    # Create MIDI state (7 channels for params + envelope)
    midi_state = MIDIState(num_channels=7)

    # Create USB MIDI driver with tap tempo
    usb_midi = USBMIDIDriver(midi_state, config, tap_note=43)
    if not usb_midi.is_connected():
        print("ERROR: USB MIDI not connected!")
        return

    print(f"✓ USB MIDI connected: {usb_midi.connected_device}")
    print(f"✓ Tap tempo enabled: Pad 8 (Note 43)")
    print()

    # Monitor loop
    print("-" * 80)
    print("Instructions:")
    print("  1. Tap Pad 8 to set tempo")
    print("  2. Turn knobs 6-8 to adjust envelope (Attack/Hold/Decay)")
    print("  3. Watch the beat trigger bar")
    print()
    print("Press Ctrl-C to exit")
    print("-" * 80)
    print()

    last_bpm = None

    try:
        while True:
            # Poll MIDI
            usb_midi.poll()

            # Get envelope parameters from MIDI state
            attack = midi_state.get_normalized(4) * 0.5   # CC4: 0-500ms
            hold = midi_state.get_normalized(5) * 0.5     # CC5: 0-500ms
            decay = midi_state.get_normalized(6) * 1.0    # CC6: 0-1000ms

            # Update envelope
            usb_midi.tap_tempo.set_envelope(attack, hold, decay)

            # Get BPM
            bpm = usb_midi.tap_tempo.get_bpm()

            # Get beat trigger
            trigger = usb_midi.tap_tempo.get_beat_trigger()

            # Display BPM if changed
            if bpm != last_bpm:
                if bpm is not None:
                    print(f"\n📊 BPM: {bpm:6.1f}")
                else:
                    print("\n⏸  Tempo timeout - tap again to restart")
                last_bpm = bpm

            # Display trigger bar (only when active)
            if bpm is not None and trigger > 0.0:
                bar = draw_trigger_bar(trigger, width=60)
                print(f"\r🎵 Trigger: {bar} {trigger:4.2f}  |  A:{attack*1000:3.0f}ms H:{hold*1000:3.0f}ms D:{decay*1000:3.0f}ms", end='', flush=True)

            time.sleep(0.01)  # 100 Hz polling

    except KeyboardInterrupt:
        print("\n\n" + "-" * 80)
        print("Test stopped")

    finally:
        usb_midi.cleanup()
        print("USB MIDI disconnected")


if __name__ == '__main__':
    main()
