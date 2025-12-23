"""Audio uniform mapping source - maps audio signals to shader uniforms.

Reads audio signals from shared memory and maps them to shader uniform parameters.
When a mapping exists, audio values override MIDI/keyboard control.
"""

from pathlib import Path
from typing import Dict, Any, Optional

import yaml

from cube.shader.uniform_sources import UniformSource
from cube.audio.shared_state import AudioStateReader

# Available audio signal names from the audio shared state
AUDIO_SIGNALS = [
    "u_audio_rms",
    "u_audio_bass",
    "u_audio_mid",
    "u_audio_high",
    "u_audio_beat_pulse",
    "u_audio_beat_phase",
    "u_audio_flux",
    "u_audio_peak",
]

# Shader uniforms that can be driven by audio
SHADER_UNIFORMS = [
    "iParam0",
    "iParam1",
    "iParam2",
    "iParam3",
    "iParam4",
    "iParam5",
    "iParam6",
    "iParam7",
    "iBeatPulse",
    "iBeatPhase",
]


class AudioUniformMappingSource(UniformSource):
    """Maps audio signals to shader uniform parameters.

    Reads audio signals from shared memory (``AudioStateReader``) and provides
    mapped uniform values. Initially all mappings are unbound (``None``).
    When a mapping exists, the audio signal value overrides MIDI/keyboard control.
    """

    def __init__(
        self,
        audio_state_reader: AudioStateReader,
        mapping_config_path: str = "audio_mapping.yml",
    ) -> None:
        """Initialize audio uniform mapping source.

        Args:
            audio_state_reader: ``AudioStateReader`` instance for reading audio signals.
            mapping_config_path: Path to YAML config file storing mappings.
        """
        self.audio_state_reader = audio_state_reader
        self.mapping_config_path = Path(mapping_config_path)
        # Ensure shared memory is attached up front; fall back gracefully.
        self._reader_ready = False
        try:
            self._reader_ready = self.audio_state_reader.initialize()
            if not self._reader_ready:
                print("[AudioUniformMappingSource] AudioStateReader initialize() failed; will retry on update")
        except Exception as e:
            print(f"[AudioUniformMappingSource] Failed to initialize AudioStateReader: {e}")
            self._reader_ready = False

        self._last_config_mtime: Optional[float] = None
        self._config_check_accumulator: float = 0.0

        # Map shader uniform name -> audio signal name or None
        self.mappings: Dict[str, Optional[str]] = {uniform: None for uniform in SHADER_UNIFORMS}

        # Latest raw audio values from shared state
        self._audio_values: Dict[str, float] = {}

        self.load_mappings()
        self._update_config_mtime()

    # ------------------------------------------------------------------
    # Config file handling
    # ------------------------------------------------------------------
    def load_mappings(self) -> None:
        """Load mappings from YAML config file.

        If the file does not exist, a default config is written.
        """
        if not self.mapping_config_path.exists():
            self.save_mappings()
            return

        try:
            with self.mapping_config_path.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:  # pragma: no cover - defensive
            print(f"Warning: Failed to load audio mappings from {self.mapping_config_path}: {e}")
            return

        mappings_section = config.get("mappings", {})
        if not isinstance(mappings_section, dict):
            return

        for uniform, signal in mappings_section.items():
            if uniform not in self.mappings:
                continue
            if signal is None or signal in AUDIO_SIGNALS:
                self.mappings[uniform] = signal

    def save_mappings(self) -> None:
        """Save mappings to YAML config file."""
        config = {"mappings": self.mappings}
        try:
            with self.mapping_config_path.open("w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            self._update_config_mtime()
        except Exception as e:  # pragma: no cover - defensive
            print(f"Error: Failed to save audio mappings to {self.mapping_config_path}: {e}")

    def _update_config_mtime(self) -> None:
        """Cache current mapping config mtime (if file exists)."""
        try:
            self._last_config_mtime = self.mapping_config_path.stat().st_mtime
        except FileNotFoundError:
            self._last_config_mtime = None

    def _maybe_reload_config(self, dt: float) -> None:
        """Periodically check for changes to the mapping config on disk.

        This allows live-updating mappings from the curses UI without
        restarting the visualization process.
        """
        self._config_check_accumulator += dt
        if self._config_check_accumulator < 0.5:
            return

        self._config_check_accumulator = 0.0

        try:
            mtime = self.mapping_config_path.stat().st_mtime
        except FileNotFoundError:
            # Config deleted; nothing to reload
            return

        if self._last_config_mtime is None:
            self._last_config_mtime = mtime
            return

        if mtime != self._last_config_mtime:
            self._last_config_mtime = mtime
            self.load_mappings()

    # ------------------------------------------------------------------
    # Public mapping API
    # ------------------------------------------------------------------
    def bind_signal(self, uniform_name: str, audio_signal_name: Optional[str]) -> None:
        """Bind an audio signal to a shader uniform.

        Args:
            uniform_name: Shader uniform name (e.g. ``"iParam0"``).
            audio_signal_name: Audio signal name (e.g. ``"u_audio_bass"``) or
                ``None`` to unbind.
        """
        if uniform_name not in self.mappings:
            raise ValueError(f"Unknown uniform: {uniform_name}")

        if audio_signal_name is not None and audio_signal_name not in AUDIO_SIGNALS:
            raise ValueError(f"Unknown audio signal: {audio_signal_name}")

        self.mappings[uniform_name] = audio_signal_name

    def unbind_signal(self, uniform_name: str) -> None:
        """Unbind a shader uniform (remove audio mapping)."""
        if uniform_name in self.mappings:
            self.mappings[uniform_name] = None

    def get_mapping(self, uniform_name: str) -> Optional[str]:
        """Get the audio signal mapped to a uniform, or ``None`` if unbound."""
        return self.mappings.get(uniform_name)

    def get_all_mappings(self) -> Dict[str, Optional[str]]:
        """Get a copy of all current mappings."""
        return self.mappings.copy()

    # ------------------------------------------------------------------
    # UniformSource interface
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Update audio signal values from shared memory.

        Args:
            dt: Delta time since last update.
        """
        if not self._reader_ready:
            try:
                self._reader_ready = self.audio_state_reader.initialize()
            except Exception as e:
                print(f"[AudioUniformMappingSource] initialize retry failed: {e}")
                self._reader_ready = False
        self._maybe_reload_config(dt)
        self._audio_values = self.audio_state_reader.read() or {}
        if not self._reader_ready:
            print("[AudioUniformMappingSource] reader not ready; using cached/empty audio values")

    def get_uniforms(self) -> Dict[str, Any]:
        """Get mapped uniform values.

        Returns only uniforms that have audio signal bindings.
        Unbound uniforms are not included (they fall back to other control
        sources like MIDI/keyboard).
        """
        uniforms: Dict[str, Any] = {}
        for uniform_name, audio_signal in self.mappings.items():
            if audio_signal is None:
                continue
            value = self._audio_values.get(audio_signal, 0.0)
            uniforms[uniform_name] = float(value)
        return uniforms

    def cleanup(self) -> None:
        """Clean up resources (no-op for this source)."""
        # Ensure shared memory is closed when visualization stops.
        try:
            self.audio_state_reader.close()
        except Exception:
            pass
        return

    def get_audio_values(self) -> Dict[str, float]:
        """Get current audio signal values (for UI display)."""
        return self._audio_values.copy()

