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

    def reset(self, default_value: int = 64):
        """Reset all CCs to default value."""
        for cc in self.cc_values:
            self.cc_values[cc] = default_value

    def __repr__(self) -> str:
        values_str = ", ".join(
            f"{self.get_cc_name(cc)}={val}"
            for cc, val in sorted(self.cc_values.items())
        )
        return f"MIDIState({values_str})"
