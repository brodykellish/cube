"""Local normalizer for adaptive signal normalization."""
import numpy as np
from collections import deque


class LocalNormalizer:
    """
    Normalizes values to maximize variance within a local time window.
    Uses mean as the baseline (10% point), biasing toward 0 while remaining
    sensitive to spikes.
    """

    def __init__(self, window_seconds=5.0, sample_rate=48000, block_size=2048, mean_output=0.1):
        blocks_per_sec = sample_rate / block_size
        self.decay_rate = 1.0 - 1.0 / (window_seconds * blocks_per_sec)
        self.mean_output = mean_output
        self.running_max = 0.01
        self.last_value = 0.0
        self.history = deque(maxlen=int(window_seconds * blocks_per_sec))

    def process(self, value):
        self.history.append(value)
        self.running_max = self.running_max * self.decay_rate + value * (1 - self.decay_rate)
        if value > self.running_max:
            self.running_max = value
        if len(self.history) < 5:
            return 0.0
        mean = np.mean(self.history)
        if mean < 0.0001:
            return 0.0
        if value <= mean:
            if mean > 0:
                normalized = self.mean_output * (value / mean)
            else:
                normalized = 0.0
        else:
            above_mean_range = self.running_max - mean
            if above_mean_range > 0.0001:
                spike_ratio = (value - mean) / above_mean_range
                normalized = self.mean_output + (1.0 - self.mean_output) * spike_ratio
            else:
                normalized = self.mean_output
        self.last_value = max(0.0, min(1.0, normalized))
        return self.last_value

    def reset(self):
        """Reset the normalizer to initial state."""
        self.running_max = 0.01
        self.history.clear()
