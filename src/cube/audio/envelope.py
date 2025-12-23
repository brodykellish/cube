"""Envelope follower for smooth signal tracking."""
import numpy as np


class EnvelopeFollower:
    """Attack/release envelope follower for smooth signal tracking."""

    def __init__(self, attack_ms=5, release_ms=150, sample_rate=48000, block_size=2048):
        blocks_per_sec = sample_rate / block_size
        self.attack = 1 - np.exp(-1 / (attack_ms * blocks_per_sec / 1000))
        self.release = 1 - np.exp(-1 / (release_ms * blocks_per_sec / 1000))
        self.value = 0.0

    def process(self, input_val):
        """Process input value through attack/release envelope."""
        if input_val > self.value:
            self.value += self.attack * (input_val - self.value)
            return self.value
        self.value += self.release * (input_val - self.value)
        return self.value
