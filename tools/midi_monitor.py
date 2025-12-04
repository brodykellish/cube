#!/usr/bin/env python3
"""
MIDI Monitor - Tool to discover MIDI CC numbers from your controller.

Usage:
    python tools/midi_monitor.py

This will display all incoming MIDI messages so you can discover which
CC numbers your faders, knobs, and buttons send.
"""

import sys
import time

try:
    import rtmidi
except ImportError:
    print("BRODY Error: python-rtmidi not installed")
    print("Install with: pip install python-rtmidi")
    sys.exit(1)


def main():
    """Run MIDI monitor."""
    print("=" * 60)
    print("MIDI Monitor - Discovering CC numbers from your controller")
    print("=" * 60)
    print()

    # Create MIDI input
    midi_in = rtmidi.MidiIn()

    # List available ports
    ports = midi_in.get_ports()

    if not ports:
        print("No MIDI devices found!")
        print("Make sure your MIDI controller is plugged in.")
        return

    print(f"Found {len(ports)} MIDI device(s):")
    for i, port in enumerate(ports):
        print(f"  {i}: {port}")
    print()

    # Select port
    if len(ports) == 1:
        port_index = 0
        print(f"Auto-selecting: {ports[0]}")
    else:
        try:
            port_index = int(input(f"Select device (0-{len(ports)-1}): "))
            if port_index < 0 or port_index >= len(ports):
                print("Invalid selection")
                return
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled")
            return

    # Open port
    try:
        midi_in.open_port(port_index)
        print(f"\nListening to: {ports[port_index]}")
        print("Move your faders, knobs, and buttons to see their CC numbers")
        print("Press Ctrl-C to exit")
        print()
        print("-" * 60)
    except Exception as e:
        print(f"Failed to open MIDI port: {e}")
        return

    # Monitor messages
    try:
        while True:
            message = midi_in.get_message()

            if message:
                midi_message, delta_time = message

                if len(midi_message) >= 3:
                    status = midi_message[0]
                    data1 = midi_message[1]
                    data2 = midi_message[2]

                    # Check if this is a Control Change message (0xB0-0xBF)
                    if (status & 0xF0) == 0xB0:
                        channel = (status & 0x0F) + 1
                        cc_number = data1
                        cc_value = data2

                        # Show message
                        print(f"CC {cc_number:3d} = {cc_value:3d}  (channel {channel})")

                    # Check if this is a Note On message (0x90-0x9F)
                    elif (status & 0xF0) == 0x90:
                        channel = (status & 0x0F) + 1
                        note = data1
                        velocity = data2

                        if velocity > 0:
                            print(f"Note {note:3d} ON  (velocity {velocity:3d}, channel {channel})")
                        else:
                            print(f"Note {note:3d} OFF (channel {channel})")

                    # Check if this is a Note Off message (0x80-0x8F)
                    elif (status & 0xF0) == 0x80:
                        channel = (status & 0x0F) + 1
                        note = data1
                        print(f"Note {note:3d} OFF (channel {channel})")

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("Monitoring stopped")

    finally:
        midi_in.close_port()
        print("MIDI port closed")


if __name__ == '__main__':
    main()
