"""
MIDI Keyboard Driver - maps laptop keys to MIDI CC changes.

Allows controlling MIDI parameters with keyboard when no USB MIDI device is available.
"""

from typing import Dict, Optional
from .midi_state import MIDIState


class MIDIKeyboardDriver:
    """
    Drives MIDI CC values from keyboard input.

    Key mappings (4 CC channels):
    - n/m: CC0 (param0) down/up
    - ,/. : CC1 (param1) down/up
    - [/] : CC2 (param2) down/up
    - ;/' : CC3 (param3) down/up
    """

    # Key mappings: key → (cc_num, delta)
    KEY_BINDINGS = {
        # CC0 - param0
        'n': (0, -5),   # Decrease
        'm': (0, +5),   # Increase

        # CC1 - param1
        ',': (1, -5),
        '.': (1, +5),

        # CC2 - param2
        '[': (2, -5),
        ']': (2, +5),

        # CC3 - param3
        ';': (3, -5),
        "'": (3, +5),
    }

    def __init__(self, midi_state: MIDIState, step_size: int = 5):
        """
        Initialize MIDI keyboard driver.

        Args:
            midi_state: MIDIState instance to update
            step_size: How much to change CC value per key press (default: 5)
        """
        self.midi_state = midi_state
        self.step_size = step_size

    def handle_key(self, key: str) -> bool:
        """
        Handle keyboard input for MIDI control.

        Args:
            key: Key name (e.g., 'n', 'm', ',', etc.)

        Returns:
            True if key was handled (is a MIDI control key), False otherwise
        """
        if key not in self.KEY_BINDINGS:
            return False

        cc_num, delta = self.KEY_BINDINGS[key]
        self.midi_state.increment_cc(cc_num, delta)

        return True

    def update_from_held_keys(self, held_keys: list, dt: float):
        """
        Update MIDI CC values from held keys (for smooth continuous adjustment).

        Args:
            held_keys: List of currently held key names
            dt: Delta time in seconds
        """
        # Scale increment based on delta time (aim for ~60 per second when held)
        increment_per_second = 60.0
        delta = int(increment_per_second * dt)
        if delta == 0:
            delta = 1  # Minimum increment

        for key in held_keys:
            if key in self.KEY_BINDINGS:
                cc_num, direction = self.KEY_BINDINGS[key]
                # direction is +5 or -5, normalize to +1 or -1 then scale by delta
                adjusted_delta = (direction // abs(direction)) * delta
                self.midi_state.increment_cc(cc_num, adjusted_delta)

    def get_cc_for_key(self, key: str) -> Optional[int]:
        """
        Get which CC number a key controls.

        Args:
            key: Key name

        Returns:
            CC number or None if key doesn't control MIDI
        """
        if key in self.KEY_BINDINGS:
            return self.KEY_BINDINGS[key][0]
        return None

    @classmethod
    def get_key_binding_display(cls) -> str:
        """
        Get formatted string showing key bindings.

        Returns:
            Human-readable key binding display
        """
        lines = [
            "MIDI Keyboard Controls:",
            "  CC0 (param0): n/m (down/up)",
            "  CC1 (param1): ,/. (down/up)",
            "  CC2 (param2): [/] (down/up)",
            "  CC3 (param3): ;/' (down/up)",
        ]
        return "\n".join(lines)
