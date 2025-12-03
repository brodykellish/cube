"""
Input source abstraction for shader uniforms.

Provides a clean interface for different types of real-time inputs:
- Keyboard/gamepad input
- Audio files (.mp3, .wav, etc.)
- Microphone input
- Camera feeds (future)

Each input source updates its own set of shader uniforms independently.
"""

import time
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class UniformSource(ABC):
    """
    Abstract base class for real-time input sources.

    Input sources provide shader uniforms that update in real-time.
    Each source is independent and can be combined with others.
    """

    @abstractmethod
    def update(self, dt: float):
        """
        Update internal state based on elapsed time.

        Args:
            dt: Delta time since last update (seconds)
        """
        pass

    @abstractmethod
    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get current uniform values.

        Returns:
            Dictionary mapping uniform name -> value
            Values can be: float, int, tuple (for vectors), numpy arrays
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up resources (close files, devices, etc.)."""
        pass

    def reset(self):
        """Reset input source to initial state (optional)."""
        pass


class KeyboardUniformSource(UniformSource):
    """
    Keyboard input source.

    Provides raw directional input as iInput uniform (vec4).
    Input values are in range [-1.0, 1.0] based on key press state.

    Uniforms provided:
    - iInput (vec4): (left/right, up/down, forward/backward, unused)
    """

    def __init__(self):
        """Initialize keyboard input source."""
        self.input_state = {
            'left': 0.0,
            'right': 0.0,
            'up': 0.0,
            'down': 0.0,
            'forward': 0.0,
            'backward': 0.0,
        }

    def set_key_state(self, key: str, pressed: bool):
        """
        Update key press state.

        Args:
            key: Key name ('left', 'right', 'up', 'down', 'forward', 'backward')
            pressed: True if key is pressed, False if released
        """
        if key in self.input_state:
            self.input_state[key] = 1.0 if pressed else 0.0

    def update(self, dt: float):
        """Update keyboard input (no-op, state updated via set_key_state)."""
        pass

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get keyboard input as iInput uniform.

        Returns:
            {'iInput': (lr, ud, fb, 0.0)}
        """
        lr = self.input_state['right'] - self.input_state['left']
        ud = self.input_state['up'] - self.input_state['down']
        fb = self.input_state['forward'] - self.input_state['backward']

        return {
            'iInput': (lr, ud, fb, 0.0)
        }

    def cleanup(self):
        """No cleanup needed for keyboard input."""
        pass

    def reset(self):
        """Reset all keys to unpressed state."""
        for key in self.input_state:
            self.input_state[key] = 0.0


class AudioFileUniformSource(UniformSource):
    """
    Audio file input source with beat detection.

    Analyzes audio file (.mp3, .wav, etc.) and provides beat-related uniforms.
    Automatically loops when audio ends.

    Uniforms provided:
    - iBPM (float): Detected beats per minute
    - iBeatPhase (float): Position in current beat cycle (0.0-1.0)
    - iBeatPulse (float): Pulse on beat (1.0 at beat, decays to 0.0)
    """

    def __init__(self, audio_path: str, bpm: Optional[float] = None):
        """
        Initialize audio file input.

        Args:
            audio_path: Path to audio file
            bpm: Manual BPM override (if None, will attempt auto-detection)
        """
        self.audio_path = Path(audio_path)
        self.manual_bpm = bpm

        # Try to import audio processor
        try:
            from .audio_processor import AudioProcessor
            self.processor = AudioProcessor(str(self.audio_path))
            self.has_audio = True
        except (ImportError, Exception) as e:
            print(f"Warning: Could not initialize audio processor: {e}")
            self.processor = None
            self.has_audio = False

        # Audio state
        self.start_time = time.time()
        self.bpm = bpm if bpm else 120.0  # Default BPM
        self.beat_phase = 0.0
        self.beat_pulse = 0.0
        self.last_beat_time = 0.0

        # If we have a processor, get actual BPM
        if self.has_audio and self.processor:
            detected_bpm = self.processor.get_bpm()
            if detected_bpm > 0:
                self.bpm = detected_bpm
            elif self.manual_bpm:
                self.bpm = self.manual_bpm

    def update(self, dt: float):
        """
        Update audio state.

        Args:
            dt: Delta time since last update
        """
        elapsed = time.time() - self.start_time

        if self.has_audio and self.processor:
            # Use audio processor for accurate beat detection
            self.beat_phase = self.processor.get_beat_phase(elapsed)
            self.beat_pulse = self.processor.get_beat_pulse(elapsed)
            self.bpm = self.processor.get_bpm()
        else:
            # Fallback: simple BPM-based beat tracking
            beat_duration = 60.0 / self.bpm
            self.beat_phase = (elapsed % beat_duration) / beat_duration

            # Simple beat pulse (1.0 at beat, decays over 0.1 seconds)
            time_since_beat = elapsed - (int(elapsed / beat_duration) * beat_duration)
            self.beat_pulse = max(0.0, 1.0 - (time_since_beat / 0.1))

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get audio uniforms.

        Returns:
            {'iBPM': float, 'iBeatPhase': float, 'iBeatPulse': float}
        """
        return {
            'iBPM': self.bpm,
            'iBeatPhase': self.beat_phase,
            'iBeatPulse': self.beat_pulse,
        }

    def cleanup(self):
        """Clean up audio processor."""
        if self.processor:
            # Processor cleanup handled automatically
            pass

    def reset(self):
        """Reset audio playback to beginning."""
        self.start_time = time.time()
        self.beat_phase = 0.0
        self.beat_pulse = 0.0


class MicrophoneUniformSource(UniformSource):
    """
    Microphone input source with real-time audio analysis.

    Captures audio from system microphone and performs real-time beat detection.

    Uniforms provided:
    - iBPM (float): Real-time detected BPM
    - iBeatPhase (float): Estimated position in beat cycle
    - iBeatPulse (float): Pulse on detected beats
    - iAudioLevel (float): Current audio level (0.0-1.0)
    - iAudioSpectrum (vec4): Frequency bands (bass, low-mid, high-mid, treble)
    """

    def __init__(self, device_index: Optional[int] = None):
        """
        Initialize microphone input.

        Args:
            device_index: Audio device index (None for default)
        """
        self.device_index = device_index

        # Try to import audio libraries
        try:
            import pyaudio
            self.has_audio = True
            self.pyaudio = pyaudio
        except ImportError:
            print("Warning: pyaudio not installed. Microphone input disabled.")
            self.has_audio = False
            self.pyaudio = None

        # Audio state
        self.bpm = 120.0
        self.beat_phase = 0.0
        self.beat_pulse = 0.0
        self.audio_level = 0.0
        self.spectrum = (0.0, 0.0, 0.0, 0.0)

        # TODO: Initialize pyaudio stream for real-time capture
        # This would require:
        # 1. Open audio stream with callback
        # 2. Perform FFT analysis in callback
        # 3. Detect beats from low-frequency energy
        # 4. Update uniforms based on analysis

        if self.has_audio:
            print("Note: MicrophoneInput is a stub. Real-time audio analysis not yet implemented.")

    def update(self, dt: float):
        """Update microphone analysis (stub)."""
        # TODO: Process audio buffer and update uniforms
        # For now, provide dummy values
        import math
        t = time.time()
        self.beat_phase = (t % 0.5) / 0.5
        self.beat_pulse = 1.0 if self.beat_phase < 0.1 else 0.0
        self.audio_level = (math.sin(t * 2) + 1) / 2

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get microphone uniforms.

        Returns:
            Dictionary with audio-related uniforms
        """
        return {
            'iBPM': self.bpm,
            'iBeatPhase': self.beat_phase,
            'iBeatPulse': self.beat_pulse,
            'iAudioLevel': self.audio_level,
            'iAudioSpectrum': self.spectrum,
        }

    def cleanup(self):
        """Clean up audio stream."""
        # TODO: Close pyaudio stream
        pass

    def reset(self):
        """Reset microphone input state."""
        self.beat_phase = 0.0
        self.beat_pulse = 0.0


class CameraUniformSource(UniformSource):
    """
    Camera input source (future implementation).

    Captures video from webcam/camera and provides as texture uniform.

    Uniforms provided:
    - iChannel0 (texture): Camera feed as texture
    - iCameraResolution (vec2): Camera resolution
    """

    def __init__(self, device_index: int = 0):
        """
        Initialize camera input.

        Args:
            device_index: Camera device index
        """
        self.device_index = device_index
        print("Note: CameraInput not yet implemented. This is a placeholder.")

    def update(self, dt: float):
        """Update camera frame (stub)."""
        pass

    def get_uniforms(self) -> Dict[str, Any]:
        """Get camera uniforms (stub)."""
        return {}

    def cleanup(self):
        """Clean up camera capture."""
        pass


class UniformSourceManager:
    """
    Manages multiple input sources and combines their uniforms.

    Allows multiple input sources to coexist (e.g., keyboard + audio).
    Each source updates independently and provides its own uniforms.
    """

    def __init__(self):
        """Initialize input manager."""
        self.sources = []

    def add_source(self, source: UniformSource):
        """
        Add an input source.

        Args:
            source: Input source to add
        """
        self.sources.append(source)

    def remove_source(self, source: UniformSource):
        """
        Remove an input source.

        Args:
            source: Input source to remove
        """
        if source in self.sources:
            source.cleanup()
            self.sources.remove(source)

    def update(self, dt: float):
        """
        Update all input sources.

        Args:
            dt: Delta time since last update
        """
        for source in self.sources:
            source.update(dt)

    def get_all_uniforms(self) -> Dict[str, Any]:
        """
        Get combined uniforms from all sources.

        If multiple sources provide the same uniform, the last one wins.

        Returns:
            Combined dictionary of all uniforms
        """
        uniforms = {}
        for source in self.sources:
            uniforms.update(source.get_uniforms())
        return uniforms

    def cleanup(self):
        """Clean up all input sources."""
        for source in self.sources:
            source.cleanup()
        self.sources.clear()

    def reset_all(self):
        """Reset all input sources to initial state."""
        for source in self.sources:
            source.reset()
