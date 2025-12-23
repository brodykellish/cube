"""Tempo tracking and beat detection."""
import time as time_module
import numpy as np
from collections import deque
from .envelope import EnvelopeFollower


class TempoTracker:
    """Tempo-locked beat tracker."""

    def __init__(self, min_bpm=60, max_bpm=200):
        self.min_bpm = min_bpm
        self.max_bpm = max_bpm
        self.prev_spectrum = None
        self.flux_envelope = EnvelopeFollower(attack_ms=2, release_ms=50)
        self.flux_history = deque(maxlen=50)
        self.onset_threshold_mult = 1.6
        self.onset_times = deque(maxlen=100)
        self.last_onset_time = 0
        self.min_onset_interval = 0.08
        self.estimated_bpm = 120.0
        self.bpm_confidence = 0.0
        self.bpm_history = deque(maxlen=30)
        self.beat_phase = 0.0
        self.last_beat_time = 0
        self.beat_count = 0
        self.phase_correction_strength = 0.15
        self.current_flux = 0.0
        self.current_onset = False
        self.phase_error_history = deque(maxlen=20)
        self.confidence_decay_rate = 0.995
        self.last_tempo_update = 0
        self.tempo_update_interval = 0.5
        self.alignment_score = 0.0
        self.beat_output_enabled = False
        self.tap_times = deque(maxlen=16)
        self.last_tap_time = 0
        self.tap_weight_max = 5.0
        self.tap_decay_time = 3.0
        self.tap_beat_triggered = False

    def reset(self):
        """Reset all tempo tracking state."""
        self.prev_spectrum = None
        self.flux_envelope = EnvelopeFollower(attack_ms=2, release_ms=50)
        self.flux_history.clear()
        self.onset_times.clear()
        self.last_onset_time = 0
        self.estimated_bpm = 120.0
        self.bpm_confidence = 0.0
        self.bpm_history.clear()
        self.beat_phase = 0.0
        self.last_beat_time = 0
        self.beat_count = 0
        self.phase_error_history.clear()
        self.last_tempo_update = 0
        self.alignment_score = 0.0
        self.current_flux = 0.0
        self.current_onset = False
        self.tap_times.clear()
        self.last_tap_time = 0
        self.tap_beat_triggered = False

    def tap(self):
        """Register a manual tap for tempo tracking."""
        current_time = time_module.time()
        if current_time - self.last_tap_time < 0.15:
            return
        self.tap_times.append(current_time)
        self.last_tap_time = current_time
        self.beat_phase = 0.0
        self.bpm_confidence = min(1.0, self.bpm_confidence + 0.15)
        self.tap_beat_triggered = True
        if len(self.tap_times) >= 2:
            times = list(self.tap_times)
            intervals = [times[i] - times[i - 1] for i in range(1, len(times))]
            valid_intervals = [i for i in intervals if 0.3 <= i <= 2.0]
            if valid_intervals:
                if len(valid_intervals) >= 2:
                    recent_interval = valid_intervals[-1]
                    median_interval = np.median(valid_intervals)
                    blended_interval = recent_interval * 0.7 + median_interval * 0.3
                else:
                    blended_interval = valid_intervals[-1]
                tap_bpm = 60.0 / blended_interval
                self.estimated_bpm = tap_bpm
                self.bpm_history.clear()
                self.bpm_history.append(tap_bpm)

    def get_tap_weight(self):
        """Calculate the current weight of manual taps (decays over time)."""
        if self.last_tap_time == 0:
            return 0.0
        time_since_tap = time_module.time() - self.last_tap_time
        weight = max(0.0, self.tap_weight_max * (1.0 - time_since_tap / self.tap_decay_time))
        if weight == 0.0 and len(self.tap_times) > 0:
            self.tap_times.clear()
        return weight

    def detect_onset(self, spectrum):
        """Detect onsets using spectral flux."""
        if self.prev_spectrum is None:
            self.prev_spectrum = spectrum.copy()
            return (False, 0.0)
        diff = spectrum - self.prev_spectrum
        flux = np.sum(np.maximum(0, diff[:len(diff) // 4]))
        self.prev_spectrum = spectrum.copy()
        smoothed_flux = self.flux_envelope.process(flux)
        self.flux_history.append(smoothed_flux)
        self.current_flux = smoothed_flux
        if len(self.flux_history) < 10:
            return (False, smoothed_flux)
        median_flux = np.median(self.flux_history)
        threshold = median_flux * self.onset_threshold_mult + 0.001
        current_time = time_module.time()
        is_onset = smoothed_flux > threshold and current_time - self.last_onset_time > self.min_onset_interval
        if is_onset:
            self.onset_times.append(current_time)
            self.last_onset_time = current_time
        self.current_onset = is_onset
        return (is_onset, smoothed_flux)

    def estimate_tempo(self):
        """Estimate BPM from onset intervals and manual taps."""
        intervals = []
        weights = []
        if len(self.onset_times) >= 2:
            times = list(self.onset_times)
            for i in range(1, len(times)):
                interval = times[i] - times[i - 1]
                if 60 / self.max_bpm <= interval <= 60 / self.min_bpm:
                    intervals.append(interval)
                    weights.append(1)
                if 60 / self.max_bpm <= interval / 2 <= 60 / self.min_bpm:
                    intervals.append(interval / 2)
                    weights.append(0.5)
                if 60 / self.max_bpm <= interval * 2 <= 60 / self.min_bpm:
                    intervals.append(interval * 2)
                    weights.append(0.5)
        if len(self.tap_times) >= 2:
            current_time = time_module.time()
            time_since_tap = current_time - self.last_tap_time
            tap_weight = max(0.0, self.tap_weight_max * (1.0 - time_since_tap / self.tap_decay_time))
            if tap_weight > 0.1:
                tap_list = list(self.tap_times)
                for i in range(1, len(tap_list)):
                    interval = tap_list[i] - tap_list[i - 1]
                    if 60 / self.max_bpm <= interval <= 60 / self.min_bpm:
                        intervals.append(interval)
                        weights.append(1.0 + tap_weight)
        if len(intervals) < 2:
            return (None, 0.0)
        intervals = np.array(intervals)
        weights = np.array(weights)
        bpm_values = 60 / intervals
        hist, bin_edges = np.histogram(bpm_values, bins=70, range=(self.min_bpm, self.max_bpm), weights=weights)
        if np.max(hist) < 2:
            return (None, 0.0)
        peak_idx = np.argmax(hist)
        peak_bpm = (bin_edges[peak_idx] + bin_edges[peak_idx + 1]) / 2
        histogram_confidence = min(1.0, np.max(hist) / 8)
        self.bpm_history.append(peak_bpm)
        return (peak_bpm, histogram_confidence)

    def update_confidence(self, phase_error, is_onset):
        """Update BPM confidence based on onset alignment."""
        self.bpm_confidence *= self.confidence_decay_rate
        if is_onset:
            error_magnitude = abs(phase_error)
            self.phase_error_history.append(error_magnitude)
            if len(self.phase_error_history) >= 3:
                avg_error = np.mean(self.phase_error_history)
                self.alignment_score = max(0.0, 1.0 - avg_error * 2)
                if avg_error < 0.15:
                    self.bpm_confidence = min(1.0, self.bpm_confidence + 0.05)
                elif avg_error > 0.3:
                    self.bpm_confidence *= 0.9

    def process(self, spectrum, dt):
        """Process spectrum and return beat information."""
        current_time = time_module.time()
        is_onset, flux = self.detect_onset(spectrum)
        should_update_tempo = (
            current_time - self.last_tempo_update > self.tempo_update_interval or
            (is_onset and self.bpm_confidence < 0.7)
        )
        if should_update_tempo:
            self.last_tempo_update = current_time
            new_bpm, histogram_conf = self.estimate_tempo()
            if new_bpm is not None:
                bpm_diff = abs(new_bpm - self.estimated_bpm)
                if self.bpm_confidence < 0.3:
                    blend = 0.3
                    self.estimated_bpm = self.estimated_bpm * (1 - blend) + new_bpm * blend
                    self.bpm_confidence = histogram_conf * 0.5
                elif bpm_diff < 5:
                    self.bpm_confidence = min(1.0, self.bpm_confidence + histogram_conf * 0.1)
                    self.estimated_bpm = self.estimated_bpm * 0.95 + new_bpm * 0.05
                elif bpm_diff > 15 and histogram_conf > self.bpm_confidence:
                    self.bpm_confidence *= 0.7
                    blend = 0.15 * histogram_conf
                    self.estimated_bpm = self.estimated_bpm * (1 - blend) + new_bpm * blend
        
        beat_period = 60.0 / self.estimated_bpm
        phase_increment = dt / beat_period
        self.beat_phase += phase_increment
        phase_error = self.beat_phase % 1.0
        if phase_error > 0.5:
            phase_error -= 1.0
        self.update_confidence(phase_error, is_onset)
        
        if is_onset and self.bpm_confidence > 0.2:
            correction_strength = self.phase_correction_strength * self.bpm_confidence
            correction = phase_error * correction_strength
            self.beat_phase -= correction
        
        is_beat = False
        if self.tap_beat_triggered:
            is_beat = True
            self.beat_count += 1
            self.last_beat_time = current_time
            self.tap_beat_triggered = False
        elif self.beat_phase >= 1.0:
            if self.beat_output_enabled:
                is_beat = True
                self.beat_count += 1
                self.last_beat_time = current_time
            self.beat_phase -= 1.0
        
        self.beat_phase = max(0.0, min(0.999, self.beat_phase))
        return (is_beat, flux, self.estimated_bpm, self.beat_phase, self.bpm_confidence)
