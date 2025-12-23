"""
Audio dashboard - combined curses UI with 2x2 quadrants.

Top-left:  Audio signal visualization (ported from audio_input UI)
Top-right: Audio → uniform mapping UI
Bottom row: Placeholders for visualization status and logs.
"""
import curses
import signal
import sys
import time
from pathlib import Path
from .app_state import AppState
from .uniform_config import create_uniform_configs
from .audio_processor import tempo_tracker
from .ui import create_draw_ui
from .shared_state import AudioStateReader, AudioControlWriter
from cube.shader.audio_uniform_mapping_source import AudioUniformMappingSource, AUDIO_SIGNALS, SHADER_UNIFORMS
from .audio_mapping_ui import draw_ui as draw_mapping_ui

shutdown_requested = False


def _signal_handler(sig, frame):
    """Handle termination signals."""
    global shutdown_requested
    print('\n[AudioDashboard] Shutdown signal received, exiting...')
    shutdown_requested = True


def _get_mapping_config_path() -> Path:
    """Get path to audio mapping config file."""
    return Path(__file__).parent.parent.parent.parent / 'audio_mapping.yml'


def _update_app_from_audio_state(app: AppState, reader: AudioStateReader):
    """Update AppState uniforms/history from shared audio state."""
    values = reader.read()
    mapping = {
        'u_audio_rms': 'rms',
        'u_audio_bass': 'bass',
        'u_audio_mid': 'mid',
        'u_audio_high': 'high',
        'u_audio_beat_pulse': 'beat_pulse',
        'u_audio_beat_phase': 'beat_phase',
        'u_audio_flux': 'spectral_flux',
        'u_audio_peak': 'peak'
    }
    for uniform_name, history_key in mapping.items():
        v = float(values.get(uniform_name, 0.0))
        app.uniforms[uniform_name] = v
        app.history[history_key].append(v)


def main(stdscr):
    """Main curses dashboard."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)
    height, width = stdscr.getmaxyx()
    half_h = max(2, height // 2)
    half_w = max(4, width // 2)
    win_audio = stdscr.subwin(half_h, half_w, 0, 0)
    win_mapping = stdscr.subwin(half_h, width - half_w, 0, half_w)
    win_vis = stdscr.subwin(height - half_h, half_w, half_h, 0)
    win_logs = stdscr.subwin(height - half_h, width - half_w, half_h, half_w)
    
    app = AppState()
    uniform_configs = create_uniform_configs()
    draw_audio_ui = create_draw_ui(app, uniform_configs, tempo_tracker)
    audio_reader = AudioStateReader()
    
    if not audio_reader.initialize(timeout=2.0):
        stdscr.addstr(0, 0, 'Error: Audio worker not running. Start audio_worker.py first.')
        stdscr.addstr(1, 0, 'Press any key to exit...')
        stdscr.getch()
        return 'Audio worker not available'
    
    control_writer = AudioControlWriter()
    control_writer.initialize()
    config_path = _get_mapping_config_path()
    mapping_source = AudioUniformMappingSource(audio_reader, str(config_path))
    selected_mapping_index = 0
    last_log = ''
    uniform_names = list(uniform_configs.keys())
    
    try:
        while not shutdown_requested:
            frame_start = time.time()
            _update_app_from_audio_state(app, audio_reader)
            mapping_source.update(0.0)
            
            try:
                draw_audio_ui(win_audio)
            except curses.error:
                pass
            
            try:
                draw_mapping_ui(win_mapping, mapping_source, selected_mapping_index)
            except curses.error:
                pass
            
            try:
                win_vis.clear()
                win_vis.border()
                win_vis.addstr(0, 2, ' Visualization (TODO) ')
            except curses.error:
                pass
            
            try:
                win_logs.clear()
                win_logs.border()
                win_logs.addstr(0, 2, ' Logs ')
                if last_log:
                    win_logs.addstr(1, 2, last_log[:width - half_w - 4])
            except curses.error:
                pass
            
            try:
                stdscr.refresh()
            except curses.error:
                pass
            
            key = stdscr.getch()
            
            if key == ord('q'):
                break
            elif key == curses.KEY_UP:
                if app.show_uniforms:
                    app.highlighted_uniform_index = (app.highlighted_uniform_index - 1) % len(uniform_names)
            elif key == curses.KEY_DOWN:
                if app.show_uniforms:
                    app.highlighted_uniform_index = (app.highlighted_uniform_index + 1) % len(uniform_names)
            elif key == ord('u'):
                app.show_uniforms = not app.show_uniforms
            elif key == ord('r'):
                control_writer.reset_tempo()
                last_log = 'Tempo reset'
            elif key == ord('b'):
                control_writer.tap_beat()
                last_log = 'Beat tap'
            elif key == ord('B'):
                control_writer.toggle_beat_output()
                last_log = 'Beat output toggled'
            elif key == ord('n'):
                if app.show_uniforms:
                    control_writer.toggle_normalized(app.highlighted_uniform_index)
                    last_log = f'Toggled normalized for {uniform_names[app.highlighted_uniform_index]}'
            elif key == ord('g'):
                if app.show_uniforms:
                    control_writer.toggle_gated(app.highlighted_uniform_index)
                    last_log = f'Toggled gated for {uniform_names[app.highlighted_uniform_index]}'
            
            num_uniforms = len(SHADER_UNIFORMS)
            if num_uniforms > 0:
                if key == curses.KEY_UP:
                    selected_mapping_index = (selected_mapping_index - 1) % num_uniforms
                elif key == curses.KEY_DOWN:
                    selected_mapping_index = (selected_mapping_index + 1) % num_uniforms
                elif key == ord('s'):
                    mapping_source.save_mappings()
                    last_log = 'Mappings saved'
                elif key == ord('U'):
                    uniform = SHADER_UNIFORMS[selected_mapping_index]
                    mapping_source.unbind_signal(uniform)
                    mapping_source.save_mappings()
                    last_log = f'Unbound {uniform}'
                elif key >= ord('0') and key <= ord('7'):
                    signal_index = key - ord('0')
                    if signal_index < len(AUDIO_SIGNALS):
                        uniform = SHADER_UNIFORMS[selected_mapping_index]
                        signal = AUDIO_SIGNALS[signal_index]
                        mapping_source.bind_signal(uniform, signal)
                        mapping_source.save_mappings()
                        last_log = f'Mapped {uniform} ← {signal}'
            
            frame_time = time.time() - frame_start
            sleep_time = max(0.0, 0.05 - frame_time)
            if sleep_time > 0:
                time.sleep(sleep_time)
    finally:
        audio_reader.close()
        control_writer.close()


def run():
    """Entry point for running the dashboard with curses.wrapper."""
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    error = curses.wrapper(main)
    if error:
        print(f'\nError: {error}')
        sys.exit(1)
