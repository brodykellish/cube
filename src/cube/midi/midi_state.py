"""
Core MIDI state - holds current CC values.

This is the single source of truth for all MIDI parameter values.
Both keyboard and USB MIDI devices update this state.
"""

from typing import Dict, Optional


class MIDIState:
    """
    Holds current MIDI Control Change (CC) values.

    This is the central state that all input sources update
    and all uniform sources read from.
    """

    # Standard MIDI CC value range
    MIN_VALUE = 0
    MAX_VALUE = 127

    # CC channel metadata (friendly names for debugging)
    CC_NAMES = {
        0: "param0",
        1: "param1",
        2: "param2",
        3: "param3",
    }

    def __init__(self, num_channels: int = 4, default_value: int = 64):
        """
        Initialize MIDI state.

        Args:
            num_channels: Number of CC channels to support (default: 4)
            default_value: Initial value for all CCs (default: 64, middle of 0-127)
        """
        self.num_channels = num_channels
        self.cc_values: Dict[int, int] = {}
        self.active_notes: Dict[int, bool] = {}  # Track which notes are currently pressed
        self._note_changes: Dict[int, bool] = {}  # Track note state changes (True = pressed, False = released)

        # Initialize all CC channels to default value
        for cc in range(num_channels):
            self.cc_values[cc] = default_value

    def set_cc(self, cc_num: int, value: int):
        """
        Set CC value (clamped to valid range).

        Args:
            cc_num: CC number (0-127)
            value: CC value (will be clamped to 0-127)
        """
        if cc_num < 0 or cc_num >= self.num_channels:
            return  # Ignore unknown CCs

        # Clamp to valid MIDI range
        clamped_value = max(self.MIN_VALUE, min(self.MAX_VALUE, value))
        self.cc_values[cc_num] = clamped_value

    def increment_cc(self, cc_num: int, delta: int = 5):
        """
        Increment CC value by delta (clamped).

        Args:
            cc_num: CC number
            delta: Amount to add (can be negative)
        """
        current = self.get_cc(cc_num)
        self.set_cc(cc_num, current + delta)

    def get_cc(self, cc_num: int) -> int:
        """
        Get current CC value.

        Args:
            cc_num: CC number

        Returns:
            CC value (0-127), or default if unknown CC
        """
        return self.cc_values.get(cc_num, 64)

    def get_cc_values(self) -> Dict[int, int]:
        """
        Get a snapshot of all CC values.

        Returns:
            Dict mapping cc_num -> value
        """
        return dict(self.cc_values)

    def get_normalized(self, cc_num: int) -> float:
        """
        Get CC value normalized to 0.0-1.0 range.

        Args:
            cc_num: CC number

        Returns:
            Normalized value (0.0-1.0)
        """
        value = self.get_cc(cc_num)
        return value / float(self.MAX_VALUE)

    def get_cc_name(self, cc_num: int) -> str:
        """Get friendly name for CC channel."""
        return self.CC_NAMES.get(cc_num, f"CC{cc_num}")

    def note_on(self, note: int):
        """
        Handle MIDI note on event.

        Args:
            note: MIDI note number (0-127)
        """
        if note < 0 or note > 127:
            return
        was_pressed = self.active_notes.get(note, False)
        if not was_pressed:
            self.active_notes[note] = True
            self._note_changes[note] = True

    def note_off(self, note: int):
        """
        Handle MIDI note off event.

        Args:
            note: MIDI note number (0-127)
        """
        if note < 0 or note > 127:
            return
        was_pressed = self.active_notes.get(note, False)
        if was_pressed:
            self.active_notes[note] = False
            self._note_changes[note] = False

    def get_active_notes(self) -> Dict[int, bool]:
        """
        Get all currently active (pressed) notes.

        Returns:
            Dict mapping note number -> True if pressed
        """
        return {note: pressed for note, pressed in self.active_notes.items() if pressed}

    def get_note_changes(self) -> Dict[int, bool]:
        """
        Get note state changes since last call and clear them.

        Returns:
            Dict mapping note number -> True if pressed, False if released
        """
        changes = dict(self._note_changes)
        self._note_changes.clear()
        return changes

    def reset(self, default_value: int = 64):
        """Reset all CCs to default value and clear all notes."""
        for cc in self.cc_values:
            self.cc_values[cc] = default_value
        self.active_notes.clear()
        self._note_changes.clear()

    def __repr__(self) -> str:
        values_str = ", ".join(
            f"{self.get_cc_name(cc)}={val}"
            for cc, val in sorted(self.cc_values.items())
        )
        active_notes_str = ", ".join(str(note) for note in sorted(self.get_active_notes().keys()))
        if active_notes_str:
            return f"MIDIState({values_str}, notes=[{active_notes_str}])"
        return f"MIDIState({values_str})"
