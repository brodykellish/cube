# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/audio/app_state.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-22 19:16:02 UTC (1766430962)

"""Application state management."""
import time as time_module
from collections import deque
from .constants import CHART_WIDTH


class AppState:
    """Global application state."""

    def __init__(self):
        self.show_uniforms = False
        self.highlighted_uniform_index = 0
        self.show_envelope = False
        self.active_envelope_param = None
        self.history = {'rms': deque([0.0] * CHART_WIDTH, maxlen=CHART_WIDTH), 'bass': deque([0.0] * CHART_WIDTH, maxlen=CHART_WIDTH), 'mid': deque([0.0] * CHART_WIDTH, maxlen=CHART_WIDTH), 'high': deque([0.0] * CHART_WIDTH, maxlen=CHART_WIDTH), 'beat_pulse': deque(
            [0.0] * CHART_WIDTH, maxlen=CHART_WIDTH), 'beat_phase': deque([0.0] * CHART_WIDTH, maxlen=CHART_WIDTH), 'spectral_flux': deque([0.0] * CHART_WIDTH, maxlen=CHART_WIDTH), 'peak': deque([0.0] * CHART_WIDTH, maxlen=CHART_WIDTH)}
        self.uniforms = {'u_audio_rms': 0.0, 'u_audio_bass': 0.0, 'u_audio_mid': 0.0, 'u_audio_high': 0.0,
                         'u_audio_beat_pulse': 0.0, 'u_audio_beat_phase': 0.0, 'u_audio_flux': 0.0, 'u_audio_peak': 0.0}
        self.auto_scale = {'rms_max': 0.01, 'bass_max': 0.0001,
                           'mid_max': 0.0001, 'high_max': 0.0001, 'flux_max': 0.01}
        self.noise_floor = None
        self.noise_floor_alpha = 0.99
        self.last_callback_time = time_module.time()
