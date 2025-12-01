"""
Mixer State - pure state container for 8-channel sequential mixer.
"""

from .mixer_channel import MixerChannel


class MixerState:
    """
    Pure state container for 8-channel sequential mixer.

    Contains 8 channels and tracks which pair is currently active for crossfading.
    Crossfader always goes 0.0 (left/lower channel) to 1.0 (right/higher channel).
    When crossfader reaches 1.0, advances to next pair.
    """

    def __init__(self, num_channels: int = 8):
        """
        Initialize mixer state with multiple channels.

        Args:
            num_channels: Number of channels (2-8)
        """
        if num_channels < 2 or num_channels > 8:
            raise ValueError("num_channels must be between 2 and 8")

        self.num_channels = num_channels
        self.channel_ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][:num_channels]

        # Create all channels
        self.channels = [MixerChannel(channel_id) for channel_id in self.channel_ids]

        # Track which pair is active (0 = channels 0-1, 1 = channels 1-2, etc.)
        self.active_pair_index: int = 0

        # Crossfader position within active pair: 0.0 = left channel, 1.0 = right channel
        self.crossfader: float = 0.0

    def get_channel(self, channel_id) -> MixerChannel:
        """
        Get channel by ID or index.

        Args:
            channel_id: Channel ID ('A'-'H') or index (0-7)

        Returns:
            MixerChannel instance
        """
        if isinstance(channel_id, int):
            if 0 <= channel_id < self.num_channels:
                return self.channels[channel_id]
            else:
                raise ValueError(f"Invalid channel index: {channel_id}")
        elif isinstance(channel_id, str):
            if channel_id in self.channel_ids:
                index = self.channel_ids.index(channel_id)
                return self.channels[index]
            else:
                raise ValueError(f"Invalid channel ID: {channel_id}")
        else:
            raise ValueError(f"channel_id must be str or int, got {type(channel_id)}")

    def get_active_pair(self) -> tuple:
        """
        Get the currently active channel pair.

        Returns:
            (left_channel, right_channel) tuple
        """
        left_index = self.active_pair_index
        right_index = self.active_pair_index + 1
        return (self.channels[left_index], self.channels[right_index])

    def get_active_pair_ids(self) -> tuple:
        """
        Get the IDs of the currently active channel pair.

        Returns:
            (left_id, right_id) tuple
        """
        left_index = self.active_pair_index
        right_index = self.active_pair_index + 1
        return (self.channel_ids[left_index], self.channel_ids[right_index])

    def set_crossfader(self, value: float):
        """
        Set crossfader value (clamped to 0.0-1.0).

        Args:
            value: 0.0 (left channel) to 1.0 (right channel)
        """
        self.crossfader = max(0.0, min(1.0, value))

    def adjust_crossfader(self, delta: float) -> bool:
        """
        Adjust crossfader by delta, with auto-advance to next pair.

        When crossfader reaches 1.0 (fully right), advances to next pair.
        When crossfader reaches 0.0 (fully left), goes back to previous pair.

        Args:
            delta: Amount to change crossfader (-1.0 to 1.0)

        Returns:
            True if pair advanced/retreated, False otherwise
        """
        new_value = self.crossfader + delta
        pair_changed = False

        # Check if we're advancing to next pair (fading right)
        if new_value >= 1.0 and delta > 0:
            # Can we advance?
            if self.active_pair_index < self.num_channels - 2:
                self.active_pair_index += 1
                self.crossfader = 0.0  # Start at left of new pair
                pair_changed = True
            else:
                # At the last pair, just clamp
                self.crossfader = 1.0
        # Check if we're retreating to previous pair (fading left)
        elif new_value <= 0.0 and delta < 0:
            # Can we retreat?
            if self.active_pair_index > 0:
                self.active_pair_index -= 1
                self.crossfader = 1.0  # Start at right of previous pair
                pair_changed = True
            else:
                # At the first pair, just clamp
                self.crossfader = 0.0
        else:
            # Normal adjustment within current pair
            self.crossfader = max(0.0, min(1.0, new_value))

        return pair_changed

    def cleanup(self):
        """Clean up all channels."""
        for channel in self.channels:
            channel.cleanup()
