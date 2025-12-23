"""
Audio mapping UI - curses interface for mapping audio signals to shader uniforms.

Runs in a separate terminal window for interactive configuration.
"""
from cube.shader.audio_uniform_mapping_source import AudioUniformMappingSource, AUDIO_SIGNALS, SHADER_UNIFORMS
from .shared_state import AudioStateReader
from typing import Optional
from pathlib import Path
import sys
import signal
import curses

shutdown_requested = False


def signal_handler(sig, frame):
    """Handle termination signals."""
    global shutdown_requested
    print('\n[AudioMappingUI] Shutdown signal received, exiting...')
    shutdown_requested = True


def get_config_path() -> Path:
    """Get path to audio mapping config file."""
    return Path(__file__).parent.parent.parent.parent / 'audio_mapping.yml'


def draw_ui(stdscr, mapping_source: AudioUniformMappingSource, selected_index: int):
    """Draw the audio mapping UI."""
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    header = 'Audio Signal Mapping'
    stdscr.addstr(0, (width - len(header)) // 2, header, curses.A_BOLD)
    stdscr.addstr(1, 0, '=' * width)
    left_col_start = 2
    right_col_start = width // 2 + 2
    col_width = (width - 4) // 2
    
    stdscr.addstr(3, left_col_start, 'Audio Signals', curses.A_BOLD | curses.A_UNDERLINE)
    row = 4
    audio_values = mapping_source.get_audio_values()
    
    for i, signal in enumerate(AUDIO_SIGNALS):
        if row >= height - 10:
            break
        is_mapped = any(mapping_source.get_mapping(uniform) == signal for uniform in SHADER_UNIFORMS)
        display_name = signal.replace('u_audio_', '')
        value = audio_values.get(signal, 0.0)
        indicator = '[→]' if is_mapped else '[ ]'
        line = f'{indicator} {display_name:20s} {value:6.3f}'
        try:
            stdscr.addstr(row, left_col_start, line[:col_width])
            row += 1
        except curses.error:
            pass
    
    stdscr.addstr(3, right_col_start, 'Shader Uniforms', curses.A_BOLD | curses.A_UNDERLINE)
    row = 4
    mappings = mapping_source.get_all_mappings()
    
    for i, uniform in enumerate(SHADER_UNIFORMS):
        if row >= height - 10:
            break
        mapped_signal = mappings.get(uniform)
        is_selected = i == selected_index
        
        if mapped_signal:
            signal_display = mapped_signal.replace('u_audio_', '')
            line = f'[→] {uniform:15s} ← {signal_display}'
            value = audio_values.get(mapped_signal, 0.0)
            value_str = f' {value:6.3f}'
        else:
            line = f'[ ] {uniform:15s}'
            value_str = ' (MIDI)'
        
        attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
        try:
            stdscr.addstr(row, right_col_start, line[:col_width], attr)
            if value_str:
                stdscr.addstr(row, right_col_start + len(line[:col_width]), value_str[:col_width - len(line[:col_width])])
            row += 1
        except curses.error:
            pass
    
    footer_y = height - 5
    try:
        stdscr.addstr(footer_y, 0, '─' * width)
        stdscr.addstr(footer_y + 1, 2, 'Controls:', curses.A_BOLD)
        stdscr.addstr(footer_y + 2, 2, '  ↑↓: Select uniform  |  0-7: Map to signal  |  u: Unbind  |  s: Save  |  q: Quit')
        signal_help = 'Signals: '
        for i, signal in enumerate(AUDIO_SIGNALS[:8]):
            display = signal.replace('u_audio_', '')[:4]
            signal_help += f'{i}:{display} '
        stdscr.addstr(footer_y + 3, 2, signal_help[:width - 4])
    except curses.error:
        pass


def main(stdscr):
    """Main function running in curses."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)
    
    audio_reader = AudioStateReader()
    if not audio_reader.initialize(timeout=2.0):
        stdscr.addstr(0, 0, 'Error: Audio process not running. Start audio_processor first.')
        stdscr.addstr(1, 0, 'Press any key to exit...')
        stdscr.getch()
        return 'Audio process not available'
    
    config_path = get_config_path()
    mapping_source = AudioUniformMappingSource(audio_reader, str(config_path))
    selected_index = 0
    
    try:
        while True:
            if shutdown_requested:
                break
            
            mapping_source.update(0.0)
            
            try:
                draw_ui(stdscr, mapping_source, selected_index)
            except curses.error:
                pass
            
            key = stdscr.getch()
            if key == curses.KEY_UP:
                selected_index = (selected_index - 1) % len(SHADER_UNIFORMS)
            elif key == curses.KEY_DOWN:
                selected_index = (selected_index + 1) % len(SHADER_UNIFORMS)
            elif key == ord('q'):
                break
            elif key == ord('s'):
                mapping_source.save_mappings()
                try:
                    stdscr.addstr(0, 0, 'Mappings saved!                                                   ')
                except curses.error:
                    pass
            elif key == ord('u'):
                uniform = SHADER_UNIFORMS[selected_index]
                mapping_source.unbind_signal(uniform)
                mapping_source.save_mappings()
            elif key >= ord('0') and key <= ord('7'):
                signal_index = key - ord('0')
                if signal_index < len(AUDIO_SIGNALS):
                    uniform = SHADER_UNIFORMS[selected_index]
                    signal = AUDIO_SIGNALS[signal_index]
                    mapping_source.bind_signal(uniform, signal)
                    mapping_source.save_mappings()
            elif key >= ord('a') and key <= ord('h'):
                signal_index = key - ord('a')
                if signal_index < len(AUDIO_SIGNALS):
                    uniform = SHADER_UNIFORMS[selected_index]
                    signal = AUDIO_SIGNALS[signal_index]
                    mapping_source.bind_signal(uniform, signal)
                    mapping_source.save_mappings()
    except KeyboardInterrupt:
        pass
    finally:
        audio_reader.close()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    error = curses.wrapper(main)
    if error:
        print(f'\nError: {error}')
        sys.exit(1)
