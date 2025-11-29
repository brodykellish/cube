"""
Audio processing for shader visualization.

Extracts audio from video files, performs FFT analysis, and provides
real-time frequency spectrum data for shader input.
"""

import numpy as np
import time
from pathlib import Path


class AudioProcessor:
    """Process audio for shader visualization."""

    def __init__(self, audio_file: str, fft_size: int = 512, sample_rate: int = 44100):
        """
        Initialize audio processor.

        Args:
            audio_file: Path to audio file (.mp4, .mp3, .wav)
            fft_size: FFT window size (power of 2)
            sample_rate: Audio sample rate
        """
        self.audio_file = Path(audio_file)
        self.fft_size = fft_size
        self.sample_rate = sample_rate

        # Audio data
        self.audio_data = None
        self.audio_length = 0
        self.current_position = 0

        # FFT spectrum (rfft returns N//2 + 1 values)
        self.spectrum_size = fft_size // 2 + 1
        self.spectrum = np.zeros(self.spectrum_size)
        self.smoothed_spectrum = np.zeros(self.spectrum_size)
        self.smooth_factor = 0.95  # Temporal smoothing (higher = smoother, 95% = very smooth)

        # BPM detection
        self.bpm = 120.0  # Detected BPM
        self.beat_phase = 0.0  # 0-1 position within current beat
        self.beat_pulse = 0.0  # 1.0 on beat, decays to 0
        self.last_beat_time = 0.0
        self.beat_interval = 0.5  # Seconds between beats (120 BPM)

        # Energy tracking for beat detection
        self.energy_history = []
        self.energy_threshold = 1.3  # Threshold multiplier for beat detection
        self.last_energy = 0.0
        self.smoothed_energy = 0.0

        # BPM estimation
        self.beat_times = []  # Timestamps of detected beats
        self.bpm_history = []  # Recent BPM estimates
        self.bpm_confidence = 0.0

        # Playback
        self.is_playing = False
        self.start_time = None
        self.pygame_loaded = False

        # Load audio
        self._load_audio()

    def _load_audio(self):
        """Load audio from file."""
        print(f"Loading audio from: {self.audio_file}")

        try:
            # Try using moviepy for video files
            if self.audio_file.suffix.lower() in ['.mp4', '.mov', '.avi']:
                try:
                    from moviepy.editor import VideoFileClip
                    video = VideoFileClip(str(self.audio_file))
                    audio = video.audio

                    # Extract audio data
                    audio_array = audio.to_soundarray(fps=self.sample_rate)

                    # Convert to mono if stereo
                    if len(audio_array.shape) > 1:
                        audio_array = audio_array.mean(axis=1)

                    self.audio_data = audio_array.astype(np.float32)
                    self.audio_length = len(self.audio_data) / self.sample_rate

                    print(f"Loaded {self.audio_length:.2f}s of audio from video")
                    video.close()

                except ImportError:
                    print("moviepy not installed. Install with: pip install moviepy")
                    raise

            # Try using librosa for audio files
            elif self.audio_file.suffix.lower() in ['.mp3', '.wav', '.ogg', '.flac']:
                try:
                    import librosa
                    audio_array, sr = librosa.load(str(self.audio_file), sr=self.sample_rate, mono=True)
                    self.audio_data = audio_array.astype(np.float32)
                    self.audio_length = len(self.audio_data) / self.sample_rate
                    print(f"Loaded {self.audio_length:.2f}s of audio")

                except ImportError:
                    print("librosa not installed. Install with: pip install librosa")
                    raise

            else:
                raise ValueError(f"Unsupported audio format: {self.audio_file.suffix}")

        except Exception as e:
            print(f"Error loading audio: {e}")
            # Create dummy audio for testing
            print("Using dummy audio (sine wave)")
            duration = 10.0  # 10 seconds
            t = np.linspace(0, duration, int(duration * self.sample_rate))
            self.audio_data = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
            self.audio_length = duration

    def start_playback(self):
        """Start audio playback."""
        if self.audio_data is None:
            return

        try:
            import pygame
            if not self.pygame_loaded:
                pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=2)
                self.pygame_loaded = True

            # Convert to int16 for pygame and duplicate mono to stereo
            audio_int16 = (self.audio_data * 32767).astype(np.int16)
            # Make stereo by duplicating mono channel
            audio_stereo = np.column_stack((audio_int16, audio_int16))
            sound = pygame.sndarray.make_sound(audio_stereo)
            sound.play()

            self.is_playing = True
            self.start_time = time.time()
            print("Audio playback started")

        except Exception as e:
            print(f"Could not start playback: {e}")
            # Still allow visualization without playback
            self.is_playing = True
            self.start_time = time.time()

    def stop_playback(self):
        """Stop audio playback."""
        if self.pygame_loaded:
            import pygame
            pygame.mixer.stop()
        self.is_playing = False

    def get_current_time(self) -> float:
        """Get current playback time in seconds."""
        if not self.is_playing or self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    def update(self) -> np.ndarray:
        """
        Update and return current frequency spectrum.

        Returns:
            Array of FFT magnitudes (fft_size // 2 values)
        """
        if self.audio_data is None:
            return self.spectrum

        # Get current time
        current_time = self.get_current_time()

        # Loop if needed
        if current_time >= self.audio_length:
            current_time = current_time % self.audio_length
            if self.is_playing:
                # Restart playback
                self.stop_playback()
                time.sleep(0.1)
                self.start_playback()

        # Get audio sample position
        sample_pos = int(current_time * self.sample_rate)

        # Extract window of audio
        if sample_pos + self.fft_size < len(self.audio_data):
            window = self.audio_data[sample_pos:sample_pos + self.fft_size]
        else:
            # Wrap around or pad
            remaining = len(self.audio_data) - sample_pos
            window = np.concatenate([
                self.audio_data[sample_pos:],
                np.zeros(self.fft_size - remaining)
            ])

        # Apply window function (Hann)
        window = window * np.hanning(self.fft_size)

        # Compute FFT
        fft = np.fft.rfft(window)
        magnitude = np.abs(fft)

        # Normalize and scale
        magnitude = magnitude / (self.fft_size / 2)

        # Apply perceptual frequency weighting to balance bass/treble
        # Create a curve that strongly reduces low frequencies for more dramatic variation
        freq_weights = np.linspace(0.2, 1.2, len(magnitude))  # 0.2 at bass, 1.2 at treble
        freq_weights = np.power(freq_weights, 0.4)  # Smooth the transition
        magnitude = magnitude * freq_weights

        magnitude = np.clip(magnitude, 0, 1)

        # Apply temporal smoothing
        self.smoothed_spectrum = (self.smooth_factor * self.smoothed_spectrum +
                                  (1 - self.smooth_factor) * magnitude)

        self.spectrum = self.smoothed_spectrum.copy()

        # Detect beats and estimate BPM
        self._detect_beat(current_time)
        self._update_beat_phase(current_time)

        return self.spectrum

    def _detect_beat(self, current_time: float):
        """Detect beats based on low frequency energy."""
        # Calculate energy in bass frequencies (first 10% of spectrum)
        bass_bins = max(1, int(self.spectrum_size * 0.1))
        energy = np.sum(self.spectrum[:bass_bins] ** 2)

        # Smooth energy
        self.smoothed_energy = 0.7 * self.smoothed_energy + 0.3 * energy

        # Keep history of recent energy (last 2 seconds)
        self.energy_history.append(self.smoothed_energy)
        history_length = int(2.0 * 60)  # ~2 seconds at 60fps
        if len(self.energy_history) > history_length:
            self.energy_history.pop(0)

        # Calculate threshold (average energy * threshold multiplier)
        if len(self.energy_history) > 10:
            avg_energy = np.mean(self.energy_history)
            threshold = avg_energy * self.energy_threshold

            # Detect beat: energy spike above threshold
            time_since_last_beat = current_time - self.last_beat_time
            min_beat_interval = 0.3  # Minimum 200 BPM (0.3s between beats)

            if (self.smoothed_energy > threshold and
                self.last_energy <= threshold and
                time_since_last_beat > min_beat_interval):

                # Beat detected!
                self.last_beat_time = current_time
                self.beat_pulse = 1.0

                # Record beat time for BPM estimation
                self.beat_times.append(current_time)

                # Keep only recent beats (last 10 seconds)
                self.beat_times = [t for t in self.beat_times if current_time - t < 10.0]

                # Estimate BPM from recent beat intervals
                if len(self.beat_times) >= 4:
                    intervals = np.diff(self.beat_times)
                    # Filter out outliers (too fast or too slow)
                    valid_intervals = [i for i in intervals if 0.3 < i < 2.0]

                    if valid_intervals:
                        avg_interval = np.median(valid_intervals)
                        estimated_bpm = 60.0 / avg_interval

                        # Smooth BPM estimate
                        self.bpm_history.append(estimated_bpm)
                        if len(self.bpm_history) > 8:
                            self.bpm_history.pop(0)

                        self.bpm = np.median(self.bpm_history)
                        self.beat_interval = 60.0 / self.bpm
                        self.bpm_confidence = min(1.0, len(self.bpm_history) / 8.0)

        self.last_energy = self.smoothed_energy

    def _update_beat_phase(self, current_time: float):
        """Update beat phase (0-1 within current beat cycle)."""
        # Calculate phase based on time since last beat
        time_since_beat = current_time - self.last_beat_time
        self.beat_phase = (time_since_beat / self.beat_interval) % 1.0

        # Decay beat pulse
        decay_rate = 5.0  # Decay speed
        dt = 1.0 / 60.0  # Assume ~60fps
        self.beat_pulse = max(0.0, self.beat_pulse - decay_rate * dt)

    def get_bpm_info(self) -> dict:
        """
        Get beat and BPM information.

        Returns:
            Dictionary with BPM, beat phase, and beat pulse
        """
        return {
            'bpm': self.bpm,
            'beat_phase': self.beat_phase,
            'beat_pulse': self.beat_pulse,
            'confidence': self.bpm_confidence
        }

    def get_spectrum_texture(self) -> np.ndarray:
        """
        Get spectrum data formatted for OpenGL texture.

        Returns:
            RGB texture data (height=1, width=spectrum_size)
        """
        # Encode spectrum in RGB (R=magnitude, G=smoothed, B=peak)
        texture_data = np.zeros((1, self.spectrum_size, 3), dtype=np.float32)
        texture_data[0, :, 0] = self.spectrum  # R: current magnitude
        texture_data[0, :, 1] = self.spectrum  # G: same for now
        texture_data[0, :, 2] = self.spectrum  # B: same for now

        return texture_data

    def close(self):
        """Clean up resources."""
        self.stop_playback()
