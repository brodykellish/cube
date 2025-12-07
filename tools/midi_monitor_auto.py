#!/usr/bin/env python3
"""
Auto MIDI Monitor - Automatically connects to Minilab3 and prints all MIDI messages.

Usage:
    python tools/midi_monitor_auto.py
"""

import sys
import time

try:
    import rtmidi
except ImportError:
    print("Error: python-rtmidi not installed")
    print("Install with: pip install python-rtmidi")
    sys.exit(1)


def main():
    """Run MIDI monitor with auto device selection."""
    print("=" * 80)
    print("MIDI Monitor - Printing all MIDI messages from your controller")
    print("=" * 80)
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

    # Auto-select Minilab3 MIDI port (index 1) or first available
    port_index = 1 if len(ports) > 1 else 0

    # Open port
    try:
        midi_in.open_port(port_index)
        print(f"Listening to: {ports[port_index]}")
        print("Move your faders, knobs, and buttons to see MIDI messages")
        print("Press Ctrl-C to exit")
        print()
        print("-" * 80)
    except Exception as e:
        print(f"Failed to open MIDI port: {e}")
        return

    # Monitor messages
    try:
        while True:
            message = midi_in.get_message()

            if message:
                midi_message, delta_time = message

                if len(midi_message) >= 1:
                    status = midi_message[0]

                    # Raw message display (useful for debugging)
                    raw_hex = ' '.join(f'{b:02X}' for b in midi_message)
                    print(f"[RAW] {raw_hex}", end='  ')

                    if len(midi_message) >= 3:
                        data1 = midi_message[1]
                        data2 = midi_message[2]

                        # Control Change (0xB0-0xBF)
                        if (status & 0xF0) == 0xB0:
                            channel = (status & 0x0F) + 1
                            cc_number = data1
                            cc_value = data2
                            print(f"→ CC#{cc_number:3d} value={cc_value:3d} (channel {channel})")

                        # Note On (0x90-0x9F)
                        elif (status & 0xF0) == 0x90:
                            channel = (status & 0x0F) + 1
                            note = data1
                            velocity = data2

                            if velocity > 0:
                                print(f"→ Note {note:3d} ON  (velocity {velocity:3d}, channel {channel})")
                            else:
                                print(f"→ Note {note:3d} OFF (channel {channel})")

                        # Note Off (0x80-0x8F)
                        elif (status & 0xF0) == 0x80:
                            channel = (status & 0x0F) + 1
                            note = data1
                            print(f"→ Note {note:3d} OFF (channel {channel})")

                        # Pitch Bend (0xE0-0xEF)
                        elif (status & 0xF0) == 0xE0:
                            channel = (status & 0x0F) + 1
                            bend_value = data1 | (data2 << 7)  # 14-bit value
                            print(f"→ Pitch Bend = {bend_value:5d} (channel {channel})")

                        # Aftertouch/Channel Pressure (0xD0-0xDF)
                        elif (status & 0xF0) == 0xD0:
                            channel = (status & 0x0F) + 1
                            pressure = data1
                            print(f"→ Channel Pressure = {pressure:3d} (channel {channel})")

                        else:
                            print(f"→ Unknown message type")

                    elif len(midi_message) == 2:
                        # Program Change (0xC0-0xCF)
                        if (status & 0xF0) == 0xC0:
                            channel = (status & 0x0F) + 1
                            program = midi_message[1]
                            print(f"→ Program Change = {program:3d} (channel {channel})")
                        else:
                            print(f"→ Unknown 2-byte message")
                    else:
                        print(f"→ System message or other")

            time.sleep(0.001)  # 1ms polling

    except KeyboardInterrupt:
        print("\n" + "-" * 80)
        print("Monitoring stopped")

    finally:
        midi_in.close_port()
        print("MIDI port closed")


if __name__ == '__main__':
    main()
