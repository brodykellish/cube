"""Uniform configuration and management."""
from .normalizer import LocalNormalizer
from .adsr_envelope import ADSREnvelope


class UniformConfig:
    """Configuration for a single uniform parameter."""

    def __init__(self, name, normalizer=None, can_gate=False, can_envelope=True):
        self.name = name
        self.can_normalize = normalizer is not None
        self.use_normalized = self.can_normalize
        self.can_gate = can_gate
        self.use_gated = False
        self.can_envelope = can_envelope
        self.use_envelope = False
        self.normalizer = normalizer
        self.envelope = ADSREnvelope()
        self.raw_value = 0.0
        self.gated_value = 0.0
        self.normalized_value = 0.0
        self.enveloped_value = 0.0

    def update(self, raw_value, gated_value=None, current_time=None):
        """Update uniform with raw and optionally gated values."""
        self.raw_value = raw_value
        self.gated_value = gated_value if gated_value is not None else raw_value
        value_to_normalize = self.gated_value if self.use_gated else raw_value
        
        if self.can_normalize:
            self.normalized_value = self.normalizer.process(value_to_normalize)
        else:
            self.normalized_value = value_to_normalize
        
        if self.use_envelope:
            self.enveloped_value = self.envelope.process(self.normalized_value, current_time)
        else:
            self.enveloped_value = self.normalized_value

    def get_value(self):
        """Get the final uniform value after all processing (normalization, gating, envelope)."""
        if self.use_envelope:
            return self.enveloped_value
        if self.use_normalized:
            return self.normalized_value
        if self.use_gated:
            return self.gated_value
        return self.raw_value

    def toggle_normalized(self):
        """Toggle normalized mode."""
        self.use_normalized = not self.use_normalized

    def toggle_gated(self):
        """Toggle gated mode."""
        if self.can_gate:
            self.use_gated = not self.use_gated

    def toggle_envelope(self):
        """Toggle envelope mode (always available for all uniforms)."""
        self.use_envelope = not self.use_envelope


def create_uniform_configs():
    """Create and return the default uniform configurations."""
    return {
        'u_audio_rms': UniformConfig('u_audio_rms', LocalNormalizer(window_seconds=3.0), can_gate=True),
        'u_audio_bass': UniformConfig('u_audio_bass', LocalNormalizer(window_seconds=3.0), can_gate=True),
        'u_audio_mid': UniformConfig('u_audio_mid', LocalNormalizer(window_seconds=3.0), can_gate=True),
        'u_audio_high': UniformConfig('u_audio_high', normalizer=None, can_gate=False),
        'u_audio_flux': UniformConfig('u_audio_flux', normalizer=None, can_gate=False),
        'u_audio_beat_pulse': UniformConfig('u_audio_beat_pulse', normalizer=None, can_gate=False),
        'u_audio_beat_phase': UniformConfig('u_audio_beat_phase', normalizer=None, can_gate=False),
        'u_audio_peak': UniformConfig('u_audio_peak', normalizer=None, can_gate=False)
    }
