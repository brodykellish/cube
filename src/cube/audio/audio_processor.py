"""Audio processing and callback logic."""
import numpy as np
import time as time_module
from .constants import BASS_RANGE, MID_RANGE, HIGH_RANGE, SCALE_DECAY
from .envelope import EnvelopeFollower
from .tempo_tracker import TempoTracker

envelopes = {
    'rms': EnvelopeFollower(attack_ms=10, release_ms=100),
    'bass': EnvelopeFollower(attack_ms=15, release_ms=120),
    'mid': EnvelopeFollower(attack_ms=10, release_ms=80),
    'high': EnvelopeFollower(attack_ms=5, release_ms=60)
}
tempo_tracker = TempoTracker()

PEAK_GATE_THRESHOLD = 0.02
PEAK_GATE_RANGE = 0.08


def freq_to_bin(freq, fft_size, sample_rate):
    """Convert frequency to FFT bin index."""
    return int(freq * fft_size / sample_rate)


def get_band_energy(spectrum, freq_range, fft_size, sample_rate):
    """Extract energy from a frequency band."""
    low_bin = max(1, freq_to_bin(freq_range[0], fft_size, sample_rate))
    high_bin = min(len(spectrum) - 1, freq_to_bin(freq_range[1], fft_size, sample_rate))
    if high_bin <= low_bin:
        return 0.0
    band = spectrum[low_bin:high_bin]
    return np.sqrt(np.mean(band ** 2))


def create_audio_callback(app, uniform_configs, samplerate):
    """Create audio callback function with closures over app state."""

    def audio_callback(indata, frames, time, status):
        """Audio callback - processes audio and updates app state."""
        current_time = time_module.time()
        dt = current_time - app.last_callback_time
        app.last_callback_time = current_time
        mono = indata.mean(axis=1)
        mono = mono - np.mean(mono)
        window = np.hanning(len(mono))
        windowed = mono * window
        raw_rms = np.sqrt(np.mean(mono ** 2))
        peak = np.max(np.abs(mono))
        fft_size = len(windowed)
        spectrum = np.abs(np.fft.rfft(windowed))
        
        if app.noise_floor is None:
            app.noise_floor = spectrum.copy()
        else:
            app.noise_floor = (
                app.noise_floor_alpha * app.noise_floor +
                (1 - app.noise_floor_alpha) * np.minimum(app.noise_floor, spectrum)
            )
        
        clean_spectrum = np.maximum(0, spectrum - app.noise_floor * 1.5)
        raw_bass = get_band_energy(clean_spectrum, BASS_RANGE, fft_size, samplerate)
        raw_mid = get_band_energy(clean_spectrum, MID_RANGE, fft_size, samplerate)
        raw_high = get_band_energy(clean_spectrum, HIGH_RANGE, fft_size, samplerate)
        
        rms = envelopes['rms'].process(raw_rms)
        bass = envelopes['bass'].process(raw_bass)
        mid = envelopes['mid'].process(raw_mid)
        high = envelopes['high'].process(raw_high)
        
        if peak < PEAK_GATE_THRESHOLD:
            gate_factor = 0.0
        elif peak > PEAK_GATE_THRESHOLD + PEAK_GATE_RANGE:
            gate_factor = 1.0
        else:
            gate_progress = (peak - PEAK_GATE_THRESHOLD) / PEAK_GATE_RANGE
            gate_factor = gate_progress ** 2
        
        rms_gated = rms * gate_factor
        bass_gated = bass * gate_factor
        mid_gated = mid * gate_factor
        high_gated = high * gate_factor
        
        is_beat, flux, bpm, phase, confidence = tempo_tracker.process(clean_spectrum, dt)
        if not tempo_tracker.beat_output_enabled:
            is_beat = False
            phase = 0.0
        
        app.auto_scale['rms_max'] = max(app.auto_scale['rms_max'] * SCALE_DECAY, rms, 0.01)
        app.auto_scale['bass_max'] = max(app.auto_scale['bass_max'] * SCALE_DECAY, bass, 0.0001)
        app.auto_scale['mid_max'] = max(app.auto_scale['mid_max'] * SCALE_DECAY, mid, 0.0001)
        app.auto_scale['high_max'] = max(app.auto_scale['high_max'] * SCALE_DECAY, high, 0.0001)
        app.auto_scale['flux_max'] = max(app.auto_scale['flux_max'] * SCALE_DECAY, flux, 0.01)
        
        norm_rms = min(1.0, rms / app.auto_scale['rms_max'])
        norm_bass = min(1.0, bass / app.auto_scale['bass_max'])
        norm_mid = min(1.0, mid / app.auto_scale['mid_max'])
        norm_high = min(1.0, high / app.auto_scale['high_max'])
        norm_flux = min(1.0, flux / app.auto_scale['flux_max'])
        norm_rms_gated = min(1.0, rms_gated / app.auto_scale['rms_max'])
        norm_bass_gated = min(1.0, bass_gated / app.auto_scale['bass_max'])
        norm_mid_gated = min(1.0, mid_gated / app.auto_scale['mid_max'])
        norm_high_gated = min(1.0, high_gated / app.auto_scale['high_max'])
        
        uniform_configs['u_audio_rms'].update(norm_rms, norm_rms_gated, current_time)
        uniform_configs['u_audio_bass'].update(norm_bass, norm_bass_gated, current_time)
        uniform_configs['u_audio_mid'].update(norm_mid, norm_mid_gated, current_time)
        uniform_configs['u_audio_high'].update(norm_high, norm_high_gated, current_time)
        uniform_configs['u_audio_beat_pulse'].update(1.0 if is_beat else 0.0, current_time=current_time)
        uniform_configs['u_audio_beat_phase'].update(phase, current_time=current_time)
        uniform_configs['u_audio_flux'].update(norm_flux, current_time=current_time)
        uniform_configs['u_audio_peak'].update(peak, current_time=current_time)
        
        for name, config in uniform_configs.items():
            app.uniforms[name] = config.get_value()
        
        app.history['rms'].append(app.uniforms['u_audio_rms'])
        app.history['bass'].append(app.uniforms['u_audio_bass'])
        app.history['mid'].append(app.uniforms['u_audio_mid'])
        app.history['high'].append(app.uniforms['u_audio_high'])
        app.history['beat_pulse'].append(app.uniforms['u_audio_beat_pulse'])
        app.history['beat_phase'].append(app.uniforms['u_audio_beat_phase'])
        app.history['spectral_flux'].append(app.uniforms['u_audio_flux'])
        app.history['peak'].append(app.uniforms['u_audio_peak'])
    
    return audio_callback
