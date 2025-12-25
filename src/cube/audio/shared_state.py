"""Shared memory state for audio uniforms - inter-process communication."""
import ctypes
import time
from multiprocessing import shared_memory
from typing import Optional


class AudioState(ctypes.Structure):
    """
    Shared memory structure for audio parameters.
    
    Uses a versioning scheme for lock-free reads:
    - Writer increments version to odd, writes data, increments to even
    - Reader checks version is even and matches before/after read
    """
    _fields_ = [
        ('version', ctypes.c_uint64),
        ('timestamp', ctypes.c_double),
        ('u_audio_rms', ctypes.c_float),
        ('u_audio_bass', ctypes.c_float),
        ('u_audio_mid', ctypes.c_float),
        ('u_audio_high', ctypes.c_float),
        ('u_audio_beat_pulse', ctypes.c_float),
        ('u_audio_beat_phase', ctypes.c_float),
        ('u_audio_flux', ctypes.c_float),
        ('u_audio_peak', ctypes.c_float),
        ('u_audio_bpm', ctypes.c_float),
        ('u_audio_confidence', ctypes.c_float)
    ]


SHARED_MEMORY_NAME = 'cube_audio_uniforms'
SHARED_MEMORY_SIZE = ctypes.sizeof(AudioState)


class AudioStateWriter:
    """Writer interface for audio process."""

    def __init__(self):
        self.shm = None
        self.state = None

    def initialize(self):
        """Create or attach to shared memory."""
        try:
            self.shm = shared_memory.SharedMemory(name=SHARED_MEMORY_NAME, create=True, size=SHARED_MEMORY_SIZE)
            self.state = AudioState.from_buffer(self.shm.buf)
            self.state.version = 0
        except FileExistsError:
            self.shm = shared_memory.SharedMemory(name=SHARED_MEMORY_NAME)
            self.state = AudioState.from_buffer(self.shm.buf)

    def update(self, uniforms: dict):
        """
        Write uniforms to shared memory with versioned consistency.
        
        Args:
            uniforms: Dictionary of uniform name -> value
        """
        if self.state is None:
            return
        self.state.version += 1
        self.state.timestamp = time.time()
        self.state.u_audio_rms = uniforms.get('u_audio_rms', 0.0)
        self.state.u_audio_bass = uniforms.get('u_audio_bass', 0.0)
        self.state.u_audio_mid = uniforms.get('u_audio_mid', 0.0)
        self.state.u_audio_high = uniforms.get('u_audio_high', 0.0)
        self.state.u_audio_beat_pulse = uniforms.get('u_audio_beat_pulse', 0.0)
        self.state.u_audio_beat_phase = uniforms.get('u_audio_beat_phase', 0.0)
        self.state.u_audio_flux = uniforms.get('u_audio_flux', 0.0)
        self.state.u_audio_peak = uniforms.get('u_audio_peak', 0.0)
        self.state.version += 1

    def close(self):
        """Close shared memory mapping in this process (does not unlink)."""
        if self.shm:
            self.state = None
            self.shm.close()
            self.shm = None

    def cleanup(self):
        """Unlink shared memory (call only once on shutdown)."""
        if self.shm:
            try:
                self.state = None
                self.shm.close()
                self.shm.unlink()
            except Exception:
                pass
            finally:
                self.shm = None
                self.state = None


class AudioStateReader:
    """Reader interface for visualization process."""

    def __init__(self):
        self.shm = None
        self.state = None
        self._cache = {}

    def initialize(self, timeout=0.1):
        """
        Attach to existing shared memory.
        
        Args:
            timeout: How long to wait for shared memory to exist (default 0.1s for non-blocking)
        
        Returns:
            True if successful, False otherwise
        """
        # If already initialized, return success
        if self.state is not None:
            return True
        
        # Try once immediately (most common case - audio process is running)
        try:
            self.shm = shared_memory.SharedMemory(name=SHARED_MEMORY_NAME)
            try:
                from multiprocessing import resource_tracker
                resource_tracker.unregister(self.shm._name, 'shared_memory')
            except Exception:
                pass
            self.state = AudioState.from_buffer(self.shm.buf)
            return True
        except FileNotFoundError:
            # If not found and timeout is very short, don't wait
            if timeout < 0.2:
                return False
            # Otherwise, try a few times with small sleep
            start = time.time()
            while time.time() - start < timeout:
                try:
                    self.shm = shared_memory.SharedMemory(name=SHARED_MEMORY_NAME)
                    try:
                        from multiprocessing import resource_tracker
                        resource_tracker.unregister(self.shm._name, 'shared_memory')
                    except Exception:
                        pass
                    self.state = AudioState.from_buffer(self.shm.buf)
                    return True
                except FileNotFoundError:
                    time.sleep(0.05)  # Shorter sleep interval
        return False

    def read(self) -> dict:
        """
        Read uniforms from shared memory with consistency check.
        
        Returns:
            Dictionary of uniform name -> value
        """
        if self.state is None:
            return self._cache
        for _ in range(3):
            version_before = self.state.version
            if version_before % 2 != 0:
                continue
            uniforms = {
                'u_audio_rms': self.state.u_audio_rms,
                'u_audio_bass': self.state.u_audio_bass,
                'u_audio_mid': self.state.u_audio_mid,
                'u_audio_high': self.state.u_audio_high,
                'u_audio_beat_pulse': self.state.u_audio_beat_pulse,
                'u_audio_beat_phase': self.state.u_audio_beat_phase,
                'u_audio_flux': self.state.u_audio_flux,
                'u_audio_peak': self.state.u_audio_peak
            }
            version_after = self.state.version
            if version_before == version_after:
                self._cache = uniforms
                return uniforms
        return self._cache

    def get_timestamp(self) -> float:
        """Get the timestamp of last update."""
        if self.state is None:
            return 0.0
        return self.state.timestamp

    def close(self):
        """Close shared memory."""
        if self.shm:
            self.state = None
            self.shm.close()
            self.shm = None


class AudioControl(ctypes.Structure):
    """
    Shared memory structure for audio control commands.
    
    Uses a versioning scheme for lock-free reads:
    - Writer increments version to odd, writes command, increments to even
    - Reader checks version is even and matches before/after read
    """
    _fields_ = [
        ('version', ctypes.c_uint64),
        ('command', ctypes.c_uint32),
        ('target_index', ctypes.c_uint32)
    ]


CONTROL_MEMORY_NAME = 'cube_audio_control'
CONTROL_MEMORY_SIZE = ctypes.sizeof(AudioControl)

CMD_NONE = 0
CMD_RESET_TEMPO = 1
CMD_TAP_BEAT = 2
CMD_TOGGLE_BEAT_OUTPUT = 3
CMD_TOGGLE_NORMALIZED = 4
CMD_TOGGLE_GATED = 5


class AudioControlWriter:
    """Writer interface for sending control commands to audio process."""

    def __init__(self):
        self.shm = None
        self.control = None

    def initialize(self):
        """Create or attach to shared memory."""
        try:
            self.shm = shared_memory.SharedMemory(name=CONTROL_MEMORY_NAME, create=True, size=CONTROL_MEMORY_SIZE)
            self.control = AudioControl.from_buffer(self.shm.buf)
            self.control.version = 0
            self.control.command = CMD_NONE
            self.control.target_index = 0
        except FileExistsError:
            self.shm = shared_memory.SharedMemory(name=CONTROL_MEMORY_NAME)
            self.control = AudioControl.from_buffer(self.shm.buf)

    def _write_command(self, command: int, target_index: int = 0):
        """Write a command to shared memory."""
        if self.control is None:
            return
        self.control.version += 1
        self.control.command = command
        self.control.target_index = target_index
        self.control.version += 1

    def reset_tempo(self):
        """Send reset tempo command."""
        self._write_command(CMD_RESET_TEMPO)

    def tap_beat(self):
        """Send tap beat command."""
        self._write_command(CMD_TAP_BEAT)

    def toggle_beat_output(self):
        """Send toggle beat output command."""
        self._write_command(CMD_TOGGLE_BEAT_OUTPUT)

    def toggle_normalized(self, target_index: int):
        """Send toggle normalized command for a specific uniform."""
        self._write_command(CMD_TOGGLE_NORMALIZED, target_index)

    def toggle_gated(self, target_index: int):
        """Send toggle gated command for a specific uniform."""
        self._write_command(CMD_TOGGLE_GATED, target_index)

    def close(self):
        """Close shared memory."""
        if self.shm:
            self.control = None
            self.shm.close()
            self.shm = None


class AudioControlReader:
    """Reader interface for receiving control commands in audio process."""

    def __init__(self):
        self.shm = None
        self.control = None
        self._last_version = 0

    def initialize(self):
        """Attach to existing shared memory."""
        try:
            self.shm = shared_memory.SharedMemory(name=CONTROL_MEMORY_NAME)
            try:
                from multiprocessing import resource_tracker
                resource_tracker.unregister(self.shm._name, 'shared_memory')
            except Exception:
                pass
            self.control = AudioControl.from_buffer(self.shm.buf)
            self._last_version = self.control.version
            return True
        except FileNotFoundError:
            return False

    def read_command(self):
        """
        Read command from shared memory.
        
        Returns:
            Tuple of (command, target_index). Returns (CMD_NONE, 0) if no new command.
        """
        if self.control is None:
            return (CMD_NONE, 0)
        
        for _ in range(3):
            version_before = self.control.version
            if version_before % 2 != 0:
                continue
            if version_before == self._last_version:
                return (CMD_NONE, 0)
            
            command = self.control.command
            target_index = self.control.target_index
            version_after = self.control.version
            
            if version_before == version_after:
                self._last_version = version_before
                return (command, target_index)
        
        return (CMD_NONE, 0)

    def close(self):
        """Close shared memory."""
        if self.shm:
            self.control = None
            self.shm.close()
            self.shm = None


def apply_audio_control_command(command: int, target_index: int, uniform_configs: dict, uniform_names: list, tempo_tracker):
    """
    Apply a control command to the audio processing system.
    
    Args:
        command: Command code (CMD_* constant)
        target_index: Target uniform index for toggle commands
        uniform_configs: Dictionary of uniform configs
        uniform_names: List of uniform names
        tempo_tracker: TempoTracker instance
    """
    if command == CMD_NONE:
        return
    elif command == CMD_RESET_TEMPO:
        tempo_tracker.reset()
    elif command == CMD_TAP_BEAT:
        tempo_tracker.tap()
    elif command == CMD_TOGGLE_BEAT_OUTPUT:
        tempo_tracker.beat_output_enabled = not tempo_tracker.beat_output_enabled
    elif command == CMD_TOGGLE_NORMALIZED:
        if 0 <= target_index < len(uniform_names):
            uniform_name = uniform_names[target_index]
            if uniform_name in uniform_configs:
                uniform_configs[uniform_name].toggle_normalized()
    elif command == CMD_TOGGLE_GATED:
        if 0 <= target_index < len(uniform_names):
            uniform_name = uniform_names[target_index]
            if uniform_name in uniform_configs:
                uniform_configs[uniform_name].toggle_gated()
