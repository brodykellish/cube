# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/audio/adsr_envelope.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-21 07:31:14 UTC (1766302274)

"""ADSR envelope generator for audio signal shaping."""
import time as time_module
import numpy as np


class ADSREnvelope:
    """ADSR (Attack, Decay, Sustain, Release) envelope generator."""

    def __init__(self, attack_ms=50, decay_ms=50, sustain=0.7, release_ms=100, width_ms=500):
        """
        Initialize ADSR envelope.

        Args:
            attack_ms: Attack time in milliseconds (0 to 1.0)
            decay_ms: Decay time in milliseconds (1.0 down to sustain level)
            sustain: Sustain level (0.0-1.0)
            release_ms: Release time in milliseconds (sustain level down to 0)
            width_ms: Total envelope width in milliseconds (100-1000ms)
        """
        self.attack_proportion = attack_ms / width_ms if width_ms > 0 else 0.1
        self.decay_proportion = decay_ms / width_ms if width_ms > 0 else 0.1
        self.release_proportion = release_ms / width_ms if width_ms > 0 else 0.2
        self.sustain = sustain
        self.width_ms = width_ms
        self.attack_ms = attack_ms
        self.decay_ms = decay_ms
        self.release_ms = release_ms
        self.state = 'idle'
        self.value = 0.0
        self.start_time = 0.0
        self.trigger_time = 0.0
        self.last_input_value = 0.0

    def set_params(self, attack_ms=None, decay_ms=None, sustain=None, release_ms=None, width_ms=None):
        """
        Update envelope parameters.

        When width_ms changes, it scales attack_ms, decay_ms, and release_ms proportionally
        by recalculating them from stored proportions.
        When attack_ms, decay_ms, or release_ms change, they update the base proportions.
        """
        old_width = self.width_ms
        if width_ms is not None:
            self.width_ms = max(100.0, min(1000.0, width_ms))
        if attack_ms is not None:
            if self.width_ms > 0:
                self.attack_proportion = attack_ms / self.width_ms
            else:
                self.attack_proportion = 0.1
        if decay_ms is not None:
            if self.width_ms > 0:
                self.decay_proportion = decay_ms / self.width_ms
            else:
                self.decay_proportion = 0.1
        if release_ms is not None:
            if self.width_ms > 0:
                self.release_proportion = release_ms / self.width_ms
            else:
                self.release_proportion = 0.2
        if sustain is not None:
            self.sustain = max(0.0, min(1.0, sustain))
        self.attack_ms = self.attack_proportion * self.width_ms
        self.decay_ms = self.decay_proportion * self.width_ms
        self.release_ms = self.release_proportion * self.width_ms

    def trigger(self, current_time=None):
        """Trigger the envelope (start attack phase)."""
        if current_time is None:
            current_time = time_module.time()
        self.trigger_time = current_time
        self.start_time = current_time
        self.state = 'attack'

    def process(self, input_value, current_time=None):
        """
        Process input value through envelope.

        For pulse trains (like beat_pulse), detects rising edges and retriggers the envelope.
        The envelope plays out its full ADSR cycle independently of the input after triggering.

        Args:
            input_value: Input signal value (0.0-1.0)
            current_time: Current time in seconds (if None, uses system time)

        Returns:
            Envelope-shaped output value (envelope value itself, not multiplied by input)
        """
        if current_time is None:
            current_time = time_module.time()
        rising_edge = input_value > 0.5 and self.last_input_value <= 0.5
        if rising_edge or (input_value > 0.1 and self.state == 'idle'):
            self.trigger(current_time)
        self.last_input_value = input_value
        elapsed = current_time - self.trigger_time
        attack_s = self.attack_ms / 1000.0
        decay_s = self.decay_ms / 1000.0
        release_s = self.release_ms / 1000.0
        width_s = self.width_ms / 1000.0
        attack_end = attack_s
        decay_end = attack_s + decay_s
        sustain_end = width_s - release_s
        release_end = width_s
        if elapsed < 0:
            self.state = 'idle'
            self.value = 0.0
            return self.value
        if elapsed < attack_end:
            self.state = 'attack'
            progress = elapsed / attack_s if attack_s > 0 else 1.0
            self.value = progress
            return self.value
        if elapsed < decay_end:
            self.state = 'decay'
            progress = (elapsed - attack_s) / decay_s if decay_s > 0 else 1.0
            self.value = 1.0 - (1.0 - self.sustain) * progress
            return self.value
        if elapsed < sustain_end:
            self.state = 'sustain'
            self.value = self.sustain
            return self.value
        if elapsed < release_end:
            self.state = 'release'
            progress = (elapsed - sustain_end) / \
                release_s if release_s > 0 else 1.0
            self.value = self.sustain * (1.0 - progress)
            return self.value
        self.state = 'idle'
        self.value = 0.0
        return self.value

    def get_state(self):
        """Get current envelope state and value."""
        return {'state': self.state, 'value': self.value, 'params': {'attack_ms': self.attack_ms, 'decay_ms': self.decay_ms, 'sustain': self.sustain, 'release_ms': self.release_ms, 'width_ms': self.width_ms}}

    def generate_waveform(self, duration=None, sample_rate=100, num_samples=None):
        """
        Generate a preview waveform of the envelope shape.

        Args:
            duration: Duration in seconds (if None, uses width_ms)
            sample_rate: Samples per second (ignored if num_samples is provided)
            num_samples: Number of samples to generate (if provided, overrides sample_rate)

        Returns:
            Array of envelope values over time
        """
        if duration is None:
            duration = self.width_ms / 1000.0
        if num_samples is not None:
            samples = num_samples
            effective_sample_rate = samples / duration
        else:
            samples = int(duration * sample_rate)
            effective_sample_rate = sample_rate
        waveform = np.zeros(samples)
        attack_s = self.attack_ms / 1000.0
        decay_s = self.decay_ms / 1000.0
        release_s = self.release_ms / 1000.0
        width_s = self.width_ms / 1000.0
        attack_end = attack_s
        decay_end = attack_s + decay_s
        sustain_end = width_s - release_s
        release_end = width_s
        for i in range(samples):
            t = i / samples * duration
            elapsed = t
            if elapsed < attack_end:
                progress = elapsed / attack_s if attack_s > 0 else 1.0
                value = progress
            elif elapsed < decay_end:
                progress = (elapsed - attack_s) / \
                    decay_s if decay_s > 0 else 1.0
                value = 1.0 - (1.0 - self.sustain) * progress
            elif elapsed < sustain_end:
                value = self.sustain
            elif elapsed < release_end:
                progress = (elapsed - sustain_end) / \
                    release_s if release_s > 0 else 1.0
                value = self.sustain * (1.0 - progress)
            else:
                value = 0.0
            waveform[i] = value
        return waveform
