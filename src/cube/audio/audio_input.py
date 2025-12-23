"""Audio input visualization - main entry point."""
import sounddevice as sd
import curses
import signal
import sys
import time
from pathlib import Path
from .constants import SAMPLERATE, BLOCKSIZE, DEVICE
from .app_state import AppState
from .uniform_config import create_uniform_configs
from .audio_processor import tempo_tracker, create_audio_callback
from .ui import create_draw_ui
from .shared_state import AudioStateWriter
from cube.midi.midi_state import MIDIState
from cube.midi.usb_driver import USBMIDIDriver
from cube.midi.config_loader import load_midi_config

shutdown_requested = False
midiout = None

try:
    import rtmidi
    from rtmidi.midiconstants import CONTROL_CHANGE
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False
    print('Warning: python-rtmidi not available. MIDI output disabled.')


def signal_handler(sig, frame):
    """Handle termination signals."""
    global shutdown_requested
    print('\n[AudioProcess] Shutdown signal received, exiting...')
    shutdown_requested = True


app = AppState()
uniform_configs = create_uniform_configs()
shared_state = AudioStateWriter()
midi_state = MIDIState()
midi_config = load_midi_config(Path(__file__).parent.parent.parent.parent / 'midi_config.yml')
usb_midi = None
if midi_config:
    usb_midi = USBMIDIDriver(midi_state, midi_config)

if RTMIDI_AVAILABLE:
    try:
        midiout = rtmidi.MidiOut()
        available_ports = midiout.get_ports()
        if available_ports:
            device_name = midi_config.device_name if midi_config else None
            port_index = 0
            if device_name:
                for i, port in enumerate(available_ports):
                    if device_name.lower() in port.lower():
                        port_index = i
                        break
            print(f'[AudioProcess] Opening MIDI output port: {available_ports[port_index]}')
            midiout.open_port(port_index)
        else:
            print('[AudioProcess] No MIDI output ports available')
            midiout = None
    except Exception as e:
        print(f'[AudioProcess] Failed to open MIDI output: {e}')
        midiout = None


def _send_midi_cc(cc_number, cc_value):
    """Send a MIDI CC message to reset controller knobs."""
    if midiout is None or not RTMIDI_AVAILABLE:
        return None
    try:
        channel = 0
        cc_value = max(0, min(127, int(cc_value)))
        message = [CONTROL_CHANGE | channel, cc_number, cc_value]
        midiout.send_message(message)
        return True
    except Exception:
        return None


def _reset_midi_knobs_for_uniform(config):
    """
    Reset MIDI controller knobs to match the current uniform's envelope parameters.
    
    This prevents parameter jumps when switching between uniforms with different
    envelope settings.
    """
    if config is None:
        return
    envelope = config.envelope
    attack_cc = int(envelope.attack_proportion / 0.3 * 127) if envelope.attack_proportion <= 0.3 else 127
    attack_cc = max(0, min(127, attack_cc))
    decay_cc = int(envelope.decay_proportion / 0.3 * 127) if envelope.decay_proportion <= 0.3 else 127
    decay_cc = max(0, min(127, decay_cc))
    sustain_cc = int(envelope.sustain * 127)
    sustain_cc = max(0, min(127, sustain_cc))
    release_cc = int(envelope.release_proportion / 0.3 * 127) if envelope.release_proportion <= 0.3 else 127
    release_cc = max(0, min(127, release_cc))
    width_cc = int((envelope.width_ms - 100.0) / 900.0 * 127)
    width_cc = max(0, min(127, width_cc))
    _send_midi_cc(93, attack_cc)
    _send_midi_cc(18, decay_cc)
    _send_midi_cc(19, sustain_cc)
    _send_midi_cc(16, release_cc)
    _send_midi_cc(82, width_cc)
    time.sleep(0.01)


def main(stdscr):
    """Main function running in curses."""
    global midiout
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(50)
    uniform_names = list(uniform_configs.keys())
    previous_highlighted_index = -1
    envelope_state = {
        'attack_proportion': 0.1,
        'decay_proportion': 0.1,
        'sustain': 0.7,
        'release_proportion': 0.2,
        'width_ms': 500.0
    }
    last_midi_cc_values = {93: None, 18: None, 19: None, 16: None, 82: None}
    shared_state.initialize()
    audio_callback = create_audio_callback(app, uniform_configs, SAMPLERATE)
    draw_ui = create_draw_ui(app, uniform_configs, tempo_tracker, midi_state)
    
    try:
        with sd.InputStream(device=DEVICE, samplerate=SAMPLERATE, blocksize=BLOCKSIZE, channels=2, callback=audio_callback):
            while True:
                if shutdown_requested:
                    print('[AudioProcess] Shutdown requested, exiting gracefully...')
                    break
                
                if usb_midi is not None:
                    usb_midi.poll()
                
                key = stdscr.getch()
                
                if app.show_uniforms:
                    highlighted_name = uniform_names[app.highlighted_uniform_index]
                    if highlighted_name in uniform_configs:
                        config = uniform_configs[highlighted_name]
                        if config.use_envelope:
                            if key == ord('a'):
                                app.active_envelope_param = None if app.active_envelope_param == 'a' else 'a'
                            elif key == ord('d'):
                                app.active_envelope_param = None if app.active_envelope_param == 'd' else 'd'
                            elif key == ord('s'):
                                app.active_envelope_param = None if app.active_envelope_param == 's' else 's'
                            elif key == ord('r'):
                                app.active_envelope_param = None if app.active_envelope_param == 'r' else 'r'
                            elif key == ord('w'):
                                app.active_envelope_param = None if app.active_envelope_param == 'w' else 'w'
                
                envelope_adjusted = False
                if app.show_uniforms and (key == curses.KEY_UP or key == curses.KEY_DOWN):
                    highlighted_name = uniform_names[app.highlighted_uniform_index]
                    if highlighted_name in uniform_configs:
                        config = uniform_configs[highlighted_name]
                        if config.use_envelope and app.active_envelope_param:
                            envelope = config.envelope
                            delta = 0.05 if key == curses.KEY_UP else -0.05
                            if app.active_envelope_param == 'a':
                                envelope_state['attack_proportion'] = max(0.0, min(0.3, envelope_state['attack_proportion'] + delta))
                                attack_ms = envelope_state['attack_proportion'] * envelope_state['width_ms']
                                envelope.set_params(attack_ms=attack_ms)
                                envelope_adjusted = True
                            elif app.active_envelope_param == 'd':
                                envelope_state['decay_proportion'] = max(0.0, min(0.3, envelope_state['decay_proportion'] + delta))
                                decay_ms = envelope_state['decay_proportion'] * envelope_state['width_ms']
                                envelope.set_params(decay_ms=decay_ms)
                                envelope_adjusted = True
                            elif app.active_envelope_param == 's':
                                envelope_state['sustain'] = max(0.0, min(1.0, envelope_state['sustain'] + delta))
                                envelope.set_params(sustain=envelope_state['sustain'])
                                envelope_adjusted = True
                            elif app.active_envelope_param == 'r':
                                envelope_state['release_proportion'] = max(0.0, min(0.3, envelope_state['release_proportion'] + delta))
                                release_ms = envelope_state['release_proportion'] * envelope_state['width_ms']
                                envelope.set_params(release_ms=release_ms)
                                envelope_adjusted = True
                            elif app.active_envelope_param == 'w':
                                envelope_state['width_ms'] = max(100.0, min(1000.0, envelope_state['width_ms'] + delta * 200.0))
                                attack_ms = envelope_state['attack_proportion'] * envelope_state['width_ms']
                                decay_ms = envelope_state['decay_proportion'] * envelope_state['width_ms']
                                release_ms = envelope_state['release_proportion'] * envelope_state['width_ms']
                                envelope.set_params(width_ms=envelope_state['width_ms'], attack_ms=attack_ms, decay_ms=decay_ms, release_ms=release_ms)
                                envelope_adjusted = True
                
                if not envelope_adjusted:
                    if key == curses.KEY_UP:
                        if app.show_uniforms:
                            app.highlighted_uniform_index = (app.highlighted_uniform_index - 1) % len(uniform_names)
                    elif key == curses.KEY_DOWN:
                        if app.show_uniforms:
                            app.highlighted_uniform_index = (app.highlighted_uniform_index + 1) % len(uniform_names)
                
                if app.show_uniforms and app.highlighted_uniform_index != previous_highlighted_index:
                    highlighted_name = uniform_names[app.highlighted_uniform_index]
                    if highlighted_name in uniform_configs:
                        config = uniform_configs[highlighted_name]
                        _reset_midi_knobs_for_uniform(config)
                        app.active_envelope_param = None
                        envelope = config.envelope
                        envelope_state['attack_proportion'] = envelope.attack_proportion
                        envelope_state['decay_proportion'] = envelope.decay_proportion
                        envelope_state['sustain'] = envelope.sustain
                        envelope_state['release_proportion'] = envelope.release_proportion
                        envelope_state['width_ms'] = envelope.width_ms
                        for cc_num in last_midi_cc_values:
                            last_midi_cc_values[cc_num] = None
                    previous_highlighted_index = app.highlighted_uniform_index
                elif key == ord('u'):
                    app.show_uniforms = not app.show_uniforms
                    if app.show_uniforms:
                        highlighted_name = uniform_names[app.highlighted_uniform_index]
                        if highlighted_name in uniform_configs:
                            config = uniform_configs[highlighted_name]
                            _reset_midi_knobs_for_uniform(config)
                            envelope = config.envelope
                            envelope_state['attack_proportion'] = envelope.attack_proportion
                            envelope_state['decay_proportion'] = envelope.decay_proportion
                            envelope_state['sustain'] = envelope.sustain
                            envelope_state['release_proportion'] = envelope.release_proportion
                            envelope_state['width_ms'] = envelope.width_ms
                            for cc_num in last_midi_cc_values:
                                last_midi_cc_values[cc_num] = None
                        previous_highlighted_index = app.highlighted_uniform_index
                elif key == ord('r'):
                    if not app.show_uniforms:
                        tempo_tracker.reset()
                elif key == ord('b'):
                    tempo_tracker.tap()
                elif key == ord('B'):
                    tempo_tracker.beat_output_enabled = not tempo_tracker.beat_output_enabled
                    if not tempo_tracker.beat_output_enabled:
                        app.uniforms['u_audio_beat_pulse'] = 0.0
                        app.uniforms['u_audio_beat_phase'] = 0.0
                elif key == ord('n'):
                    if app.show_uniforms:
                        highlighted_name = uniform_names[app.highlighted_uniform_index]
                        if highlighted_name in uniform_configs:
                            uniform_configs[highlighted_name].toggle_normalized()
                elif key == ord('g'):
                    if app.show_uniforms:
                        highlighted_name = uniform_names[app.highlighted_uniform_index]
                        if highlighted_name in uniform_configs:
                            uniform_configs[highlighted_name].toggle_gated()
                elif key == ord('p'):
                    if app.show_uniforms:
                        highlighted_name = uniform_names[app.highlighted_uniform_index]
                        if highlighted_name in uniform_configs:
                            config = uniform_configs[highlighted_name]
                            config.toggle_envelope()
                            app.show_envelope = config.use_envelope
                            app.active_envelope_param = None
                            envelope = config.envelope
                            envelope_state['attack_proportion'] = envelope.attack_proportion
                            envelope_state['decay_proportion'] = envelope.decay_proportion
                            envelope_state['sustain'] = envelope.sustain
                            envelope_state['release_proportion'] = envelope.release_proportion
                            envelope_state['width_ms'] = envelope.width_ms
                            for cc_num in last_midi_cc_values:
                                last_midi_cc_values[cc_num] = None
                        else:
                            app.show_envelope = False
                    else:
                        app.show_envelope = False
                elif key == ord('q'):
                    break
                
                if app.show_uniforms:
                    highlighted_name = uniform_names[app.highlighted_uniform_index]
                    if highlighted_name in uniform_configs:
                        config = uniform_configs[highlighted_name]
                        envelope = config.envelope
                        attack_cc = midi_state.get_cc(93)
                        decay_cc = midi_state.get_cc(18)
                        sustain_cc = midi_state.get_cc(19)
                        release_cc = midi_state.get_cc(16)
                        width_cc = midi_state.get_cc(82)
                        params_updated = False
                        
                        if last_midi_cc_values[93] is not None and attack_cc != last_midi_cc_values[93]:
                            relative_delta = attack_cc - 64
                            if relative_delta != 0:
                                proportion_delta = relative_delta / 64.0 * 0.05
                                envelope_state['attack_proportion'] = max(0.0, min(0.3, envelope_state['attack_proportion'] + proportion_delta))
                                params_updated = True
                        if last_midi_cc_values[18] is not None and decay_cc != last_midi_cc_values[18]:
                            relative_delta = decay_cc - 64
                            if relative_delta != 0:
                                proportion_delta = relative_delta / 64.0 * 0.05
                                envelope_state['decay_proportion'] = max(0.0, min(0.3, envelope_state['decay_proportion'] + proportion_delta))
                                params_updated = True
                        if last_midi_cc_values[19] is not None and sustain_cc != last_midi_cc_values[19]:
                            relative_delta = sustain_cc - 64
                            if relative_delta != 0:
                                sustain_delta = relative_delta / 64.0 * 0.05
                                envelope_state['sustain'] = max(0.0, min(1.0, envelope_state['sustain'] + sustain_delta))
                                params_updated = True
                        if last_midi_cc_values[16] is not None and release_cc != last_midi_cc_values[16]:
                            relative_delta = release_cc - 64
                            if relative_delta != 0:
                                proportion_delta = relative_delta / 64.0 * 0.05
                                envelope_state['release_proportion'] = max(0.0, min(0.3, envelope_state['release_proportion'] + proportion_delta))
                                params_updated = True
                        if last_midi_cc_values[82] is not None and width_cc != last_midi_cc_values[82]:
                            relative_delta = width_cc - 64
                            if relative_delta != 0:
                                width_delta = relative_delta / 64.0 * 200.0
                                envelope_state['width_ms'] = max(100.0, min(1000.0, envelope_state['width_ms'] + width_delta))
                                params_updated = True
                        
                        if params_updated:
                            attack_ms = envelope_state['attack_proportion'] * envelope_state['width_ms']
                            decay_ms = envelope_state['decay_proportion'] * envelope_state['width_ms']
                            release_ms = envelope_state['release_proportion'] * envelope_state['width_ms']
                            envelope.set_params(
                                width_ms=envelope_state['width_ms'],
                                attack_ms=attack_ms,
                                decay_ms=decay_ms,
                                sustain=envelope_state['sustain'],
                                release_ms=release_ms
                            )
                        last_midi_cc_values[93] = attack_cc
                        last_midi_cc_values[18] = decay_cc
                        last_midi_cc_values[19] = sustain_cc
                        last_midi_cc_values[16] = release_cc
                        last_midi_cc_values[82] = width_cc
                
                shared_state.update(app.uniforms)
                try:
                    draw_ui(stdscr)
                except curses.error:
                    pass
    except Exception as e:
        shared_state.cleanup()
        return str(e)
    finally:
        if midiout is not None:
            try:
                midiout.close_port()
            except Exception:
                pass
            del midiout
            midiout = None
        shared_state.cleanup()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    error = curses.wrapper(main)
    if error:
        print(f'\nError: {error}')
        print('\nAvailable devices:')
        print(sd.query_devices())
