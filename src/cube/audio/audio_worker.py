"""
Headless audio worker process.

Runs the audio signal processing pipeline (sounddevice input, FFT, tempo
tracking) and writes audio uniforms to shared memory. Configuration is
controlled via the shared AudioControl channel.
"""
import signal
import sys
import time
import traceback
import sounddevice as sd
from .constants import SAMPLERATE, BLOCKSIZE, DEVICE
from .app_state import AppState
from .uniform_config import create_uniform_configs
from .audio_processor import tempo_tracker, create_audio_callback
from .shared_state import AudioStateWriter, AudioControlReader, CMD_NONE, apply_audio_control_command

shutdown_requested = False


def _signal_handler(sig, frame):
    """Handle termination signals."""
    global shutdown_requested
    print('\n[AudioWorker] Shutdown signal received, exiting...')
    shutdown_requested = True


def main():
    """Main entry point for the headless audio worker."""
    app = AppState()
    uniform_configs = create_uniform_configs()
    state_writer = AudioStateWriter()
    control_reader = AudioControlReader()
    state_writer.initialize()
    control_reader.initialize()
    audio_callback = create_audio_callback(app, uniform_configs, SAMPLERATE)
    uniform_names = list(uniform_configs.keys())
    
    try:
        with sd.InputStream(device=DEVICE, samplerate=SAMPLERATE, blocksize=BLOCKSIZE, channels=2, callback=audio_callback):
            last_state_update = time.time()
            while not shutdown_requested:
                now = time.time()
                if now - last_state_update >= 0.01:
                    state_writer.update(app.uniforms)
                    last_state_update = now
                command, target_index = control_reader.read_command()
                if command != CMD_NONE:
                    apply_audio_control_command(command, target_index, uniform_configs, uniform_names, tempo_tracker)
                time.sleep(0.005)
    except Exception as e:
        print(f'[AudioWorker] Error: {e}')
        traceback.print_exc()
    finally:
        state_writer.cleanup()
        control_reader.close()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    main()
