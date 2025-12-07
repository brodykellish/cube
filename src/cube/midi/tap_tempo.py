"""
Tap Tempo Detector - calculates BPM from tap timing and generates beat triggers.

Analyzes tap intervals to determine tempo in beats per minute.
Generates beat triggers with configurable ADSR envelope.
"""

import time
from typing import List, Optional
from collections import deque


class TapTempoDetector:
    """
    Detects BPM from tap input timing and generates beat triggers.

    Calculates tempo by analyzing intervals between taps.
    Generates a beat trigger (0.0-1.0) that spikes on each beat with ADSR envelope.
    Uses a sliding window of recent taps for smooth BPM tracking.
    """

    def __init__(self, tempo_window: float = 3.0, hold_to_clear_duration: float = 3.0):
        """
        Initialize tap tempo detector.

        Args:
            tempo_window: Time window for calculating tempo (seconds)
            hold_to_clear_duration: Time to hold pad to clear tempo (seconds)
        """
        self.tempo_window = tempo_window
        self.hold_to_clear_duration = hold_to_clear_duration

        # Tap timestamps (in seconds) - no maxlen, we'll filter by time window
        self.tap_times: deque[float] = deque()

        # Current calculated BPM
        self.bpm: Optional[float] = None

        # Last tap time (for building tap history)
        self.last_tap_time: Optional[float] = None

        # Beat tracking for trigger generation
        self.last_beat_time: Optional[float] = None
        self.beat_duration: Optional[float] = None  # Duration in seconds

        # Note hold tracking (for hold-to-clear)
        self.note_press_time: Optional[float] = None
        self.note_is_held: bool = False

        # ADSR envelope parameters (in seconds)
        self.attack_time: float = 0.05   # Time to reach peak (50ms default)
        self.hold_time: float = 0.1      # Time to hold at peak (100ms default)
        self.decay_time: float = 0.2     # Time to decay to zero (200ms default)

    def note_on(self):
        """
        Called when tap note is pressed.

        Registers a tap and starts tracking hold duration.
        """
        current_time = time.time()

        # Start tracking note hold
        self.note_press_time = current_time
        self.note_is_held = True

        # Register tap
        self.tap_times.append(current_time)
        self.last_tap_time = current_time

        # Calculate BPM if we have at least 2 taps
        if len(self.tap_times) >= 2:
            self._calculate_bpm()

    def note_off(self):
        """
        Called when tap note is released.
        """
        self.note_is_held = False
        self.note_press_time = None

    def check_hold_to_clear(self) -> bool:
        """
        Check if note has been held long enough to clear tempo.

        Returns:
            True if tempo was cleared, False otherwise
        """
        if not self.note_is_held or self.note_press_time is None:
            return False

        hold_duration = time.time() - self.note_press_time

        if hold_duration >= self.hold_to_clear_duration:
            print(f"⏸  Tempo cleared (held for {hold_duration:.1f}s)")
            self.reset()
            self.note_is_held = False
            self.note_press_time = None
            return True

        return False

    def _calculate_bpm(self):
        """
        Calculate BPM from tap intervals within the tempo window.

        Only uses taps from the last tempo_window seconds.
        Does not update BPM if insufficient recent taps.
        """
        current_time = time.time()

        # Remove taps older than tempo_window
        while self.tap_times and (current_time - self.tap_times[0]) > self.tempo_window:
            self.tap_times.popleft()

        # Get taps within the tempo window
        recent_taps = list(self.tap_times)

        # Need at least 2 taps to calculate tempo
        if len(recent_taps) < 2:
            return  # Don't modify existing tempo

        # Calculate intervals between consecutive taps
        intervals = []
        for i in range(1, len(recent_taps)):
            interval = recent_taps[i] - recent_taps[i-1]
            intervals.append(interval)

        if not intervals:
            return

        # Average interval (in seconds)
        avg_interval = sum(intervals) / len(intervals)

        # Convert to BPM (60 seconds per minute / interval per beat)
        self.bpm = 60.0 / avg_interval

        # Clamp to reasonable range (20-300 BPM)
        self.bpm = max(20.0, min(300.0, self.bpm))

        # Store beat duration
        self.beat_duration = 60.0 / self.bpm

        # Initialize beat tracking
        if self.last_beat_time is None:
            self.last_beat_time = time.time()

    def get_bpm(self) -> Optional[float]:
        """
        Get current detected BPM.

        Returns:
            BPM as float, or None if no tempo detected yet
        """
        return self.bpm

    def get_beat_duration(self) -> Optional[float]:
        """
        Get duration of one beat in seconds.

        Returns:
            Beat duration, or None if no tempo detected
        """
        return self.beat_duration

    def set_envelope(self, attack: float, hold: float, decay: float):
        """
        Set ADSR envelope parameters.

        Args:
            attack: Attack time in seconds (0.0-1.0)
            hold: Hold time in seconds (0.0-1.0)
            decay: Decay time in seconds (0.0-1.0)
        """
        self.attack_time = attack
        self.hold_time = hold
        self.decay_time = decay

    def get_beat_trigger(self) -> float:
        """
        Get current beat trigger value (0.0-1.0) with ADSR envelope.

        Returns:
            Beat trigger value (0.0 = silent, 1.0 = peak)
            Returns 0.0 if no tempo detected
        """
        # Check if user is holding to clear
        self.check_hold_to_clear()

        # No tempo detected
        if self.bpm is None or self.beat_duration is None:
            return 0.0

        current_time = time.time()

        # Calculate time since last beat
        if self.last_beat_time is None:
            self.last_beat_time = current_time

        time_since_beat = current_time - self.last_beat_time

        # Check if we need to trigger a new beat
        if time_since_beat >= self.beat_duration:
            # Advance to next beat
            self.last_beat_time += self.beat_duration
            time_since_beat = current_time - self.last_beat_time

        # Calculate ADSR envelope
        total_envelope_time = self.attack_time + self.hold_time + self.decay_time

        # Make sure envelope fits within beat duration
        if total_envelope_time > self.beat_duration:
            # Scale down envelope to fit
            scale = self.beat_duration / total_envelope_time
            attack_time = self.attack_time * scale
            hold_time = self.hold_time * scale
            decay_time = self.decay_time * scale
        else:
            attack_time = self.attack_time
            hold_time = self.hold_time
            decay_time = self.decay_time

        # ADSR stages
        if time_since_beat < attack_time:
            # Attack: 0.0 -> 1.0
            if attack_time > 0:
                return time_since_beat / attack_time
            else:
                return 1.0

        elif time_since_beat < attack_time + hold_time:
            # Hold: 1.0
            return 1.0

        elif time_since_beat < attack_time + hold_time + decay_time:
            # Decay: 1.0 -> 0.0
            decay_phase = time_since_beat - attack_time - hold_time
            if decay_time > 0:
                return 1.0 - (decay_phase / decay_time)
            else:
                return 0.0

        else:
            # Silence until next beat
            return 0.0

    def reset(self):
        """Reset tap history and BPM."""
        self.tap_times.clear()
        self.bpm = None
        self.last_tap_time = None
        self.last_beat_time = None
        self.beat_duration = None

    def __repr__(self) -> str:
        if self.bpm is None:
            return "TapTempoDetector(no tempo)"
        # Count recent taps within tempo window
        current_time = time.time()
        recent_count = sum(1 for t in self.tap_times if (current_time - t) <= self.tempo_window)
        return f"TapTempoDetector(BPM={self.bpm:.1f}, recent_taps={recent_count}/{len(self.tap_times)})"
