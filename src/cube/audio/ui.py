"""UI rendering functions and helpers."""
import curses
from .constants import CHART_WIDTH


def make_bar(value, width=30, char='█', empty_char='░'):
    """Create a simple bar visualization."""
    clamped = max(0.0, min(1.0, value))
    filled = int(clamped * width)
    return char * filled + empty_char * (width - filled)


def make_gradient_bar(value, width=40):
    """Create a gradient bar with different characters for different levels."""
    clamped = max(0.0, min(1.0, value))
    filled = int(clamped * width)
    bar = ''
    for i in range(width):
        if i < filled:
            if i < width * 0.5:
                bar += '▓'
            elif i < width * 0.75:
                bar += '▒'
            else:
                bar += '░'
        else:
            bar += '·'
    return bar


def make_phase_indicator(phase, width=40):
    """Create a phase indicator showing position in beat cycle."""
    pos = int(phase * width)
    return '─' * pos + '●' + '─' * (width - pos - 1)


def make_chart(values, height=4, width=None):
    """Create ASCII chart from values."""
    if width is None:
        width = len(values)
    vals = list(values)[-width:]
    if len(vals) < width:
        vals = [0.0] * (width - len(vals)) + vals
    blocks = ' ▁▂▃▄▅▆▇█'
    lines = []
    for row in range(height - 1, -1, -1):
        line = ''
        row_bottom = row / height
        row_top = (row + 1) / height
        for val in vals:
            if val >= row_top:
                line += blocks[-1]
            elif val > row_bottom:
                partial = (val - row_bottom) / (row_top - row_bottom)
                idx = int(partial * (len(blocks) - 1))
                line += blocks[idx]
            else:
                line += ' '
        lines.append(line)
    return lines


def create_draw_ui(app, uniform_configs, tempo_tracker, midi_state=None):
    """Create draw_ui function with closures over app state."""

    def draw_ui(stdscr):
        """Draw the UI using curses, filling available terminal height."""
        stdscr.clear()
        term_height, term_width = stdscr.getmaxyx()
        HEADER_LINES = 4
        FOOTER_LINES = 2
        content_height = term_height - HEADER_LINES - FOOTER_LINES
        uniform_names = list(uniform_configs.keys())
        bpm = tempo_tracker.estimated_bpm
        confidence = tempo_tracker.bpm_confidence
        phase = tempo_tracker.beat_phase
        is_beat = app.uniforms.get('u_audio_beat_pulse', 0) > 0.5
        row = 0
        
        stdscr.addstr(row, 0, '════════════════════════════════════════════════════════════════')
        row += 1
        stdscr.addstr(row, 0, '  AUDIO VISUALIZATION                                            ')
        row += 1
        stdscr.addstr(row, 0, '════════════════════════════════════════════════════════════════')
        row += 2
        
        if app.show_uniforms:
            FIXED_CHART_HEIGHT = 5
            CHART_WIDTH_WITH_BORDERS = 54
            CHART_HEADER_HEIGHT = 1
            CHART_TOTAL_HEIGHT = FIXED_CHART_HEIGHT + CHART_HEADER_HEIGHT
            uniforms_box_lines = len(uniform_configs) + 3
            selection_lines = 2
            envelope_height = 0
            highlighted_name = uniform_names[app.highlighted_uniform_index]
            config = uniform_configs.get(highlighted_name)
            if config and app.show_envelope and config.use_envelope:
                envelope_height = 17
            remaining_for_charts = content_height - uniforms_box_lines - selection_lines - envelope_height
            charts_per_column = max(1, remaining_for_charts // CHART_TOTAL_HEIGHT)
            charts_per_row = max(1, term_width // CHART_WIDTH_WITH_BORDERS)
            all_charts = [
                ('u_audio_rms', 'rms'),
                ('u_audio_bass', 'bass'),
                ('u_audio_mid', 'mid'),
                ('u_audio_high', 'high'),
                ('u_audio_flux', 'spectral_flux'),
                ('u_audio_beat_pulse', 'beat_pulse'),
                ('u_audio_beat_phase', 'beat_phase'),
                ('u_audio_peak', 'peak')
            ]
            
            stdscr.addstr(row, 0, '  ╔════════════════════════════════════════════════════════════╗')
            row += 1
            stdscr.addstr(row, 0, '  ║  SHADER UNIFORMS                                           ║')
            row += 1
            stdscr.addstr(row, 0, '  ╠════════════════════════════════════════════════════════════╣')
            row += 1
            
            for i, (name, config) in enumerate(uniform_configs.items()):
                value = config.get_value()
                bar = make_gradient_bar(value, 25)
                mode_parts = []
                if config.can_normalize:
                    norm_mode = 'N' if config.use_normalized else 'R'
                    mode_parts.append(norm_mode)
                if config.can_gate:
                    gate_mode = 'G' if config.use_gated else 'U'
                    mode_parts.append(gate_mode)
                if config.use_envelope:
                    mode_parts.append('E')
                if mode_parts:
                    mode = '/'.join(mode_parts) + ' ' * (3 - len(mode_parts))
                else:
                    mode = '   '
                
                if app.show_uniforms and i == app.highlighted_uniform_index:
                    marker = '▶'
                    attr = curses.A_REVERSE
                else:
                    marker = ' '
                    attr = curses.A_NORMAL
                
                line = f'  ║{marker} {name:<20} {bar} {value:.3f} [{mode}] ║'
                stdscr.addstr(row, 0, line, attr)
                row += 1
            
            stdscr.addstr(row, 0, '  ╚════════════════════════════════════════════════════════════╝')
            row += 1
            
            highlighted_name = uniform_names[app.highlighted_uniform_index]
            config = uniform_configs.get(highlighted_name)
            if config:
                row += 1
                status_parts = []
                if config.can_normalize:
                    mode_str = 'NORMALIZED' if config.use_normalized else 'RAW'
                    status_parts.append(mode_str)
                if config.can_gate:
                    gate_str = 'GATED' if config.use_gated else 'UNGATED'
                    status_parts.append(gate_str)
                env_str = 'ENVELOPE' if config.use_envelope else 'NO ENVELOPE'
                status_parts.append(env_str)
                status = ', '.join(status_parts) if status_parts else 'NO CONTROLS'
                
                help_parts = []
                if config.can_normalize:
                    help_parts.append('\'n\' norm/raw')
                if config.can_gate:
                    help_parts.append('\'g\' gate')
                help_parts.append('\'p\' envelope')
                help_str = ' | '.join(help_parts) if help_parts else 'read-only'
                help_text = f'  ▶ {highlighted_name} [{status}] - {help_str}'
                stdscr.addstr(row, 0, help_text)
                row += 1
                
                if app.show_envelope and config.use_envelope:
                    row += 1
                    stdscr.addstr(row, 0, '  ╔════════════════════════════════════════════════════════════╗')
                    row += 1
                    active_param = app.active_envelope_param
                    if active_param:
                        mode_names = {'a': 'ATTACK', 'd': 'DECAY', 's': 'SUSTAIN', 'r': 'RELEASE', 'w': 'WIDTH'}
                        mode_text = f' [{mode_names[active_param]}]'
                        header_text = f'  ║  ENVELOPE SHAPE{mode_text:<45}║'
                        stdscr.addstr(row, 0, header_text, curses.A_BOLD | curses.A_REVERSE)
                    else:
                        stdscr.addstr(row, 0, '  ║  ENVELOPE SHAPE                                                  ║')
                    row += 1
                    stdscr.addstr(row, 0, '  ╠════════════════════════════════════════════════════════════╣')
                    row += 1
                    
                    env_state = config.envelope.get_state()
                    params = env_state['params']
                    attack_ms = params['attack_ms']
                    decay_ms = params['decay_ms']
                    sustain_pct = params['sustain'] * 100
                    release_ms = params['release_ms']
                    width_ms = params['width_ms']
                    
                    stdscr.addstr(row, 0, f'  ║  Attack:  {attack_ms:6.1f}ms  Decay: {decay_ms:6.1f}ms  Sustain: {sustain_pct:5.1f}%  ║')
                    row += 1
                    stdscr.addstr(row, 0, f'  ║  Release: {release_ms:6.1f}ms  Width:  {width_ms:6.1f}ms                          ║')
                    row += 1
                    stdscr.addstr(row, 0, '  ╠════════════════════════════════════════════════════════════╣')
                    row += 1
                    
                    total_duration = width_ms / 1000.0
                    waveform = config.envelope.generate_waveform(duration=total_duration, num_samples=CHART_WIDTH)
                    for line in make_chart(waveform, height=8, width=CHART_WIDTH):
                        if row < term_height - FOOTER_LINES - 1:
                            try:
                                stdscr.addstr(row, 0, f'  ║│{line}│║')
                                row += 1
                            except curses.error:
                                pass
                        else:
                            break
                    
                    stdscr.addstr(row, 0, '  ╚════════════════════════════════════════════════════════════╝')
                    row += 1
                    
                    active_param = app.active_envelope_param
                    if active_param:
                        param_names = {'a': 'Attack', 'd': 'Decay', 's': 'Sustain', 'r': 'Release', 'w': 'Width'}
                        current_param = param_names[active_param]
                        row += 1
                        help_text = f'  Adjusting {current_param}: ↑↓ to modify | \'{active_param}\' to exit | \'a\'/\'d\'/\'s\'/\'r\'/\'w\' to switch'
                        stdscr.addstr(row, 0, help_text, curses.A_BOLD)
                    else:
                        row += 1
                        help_text = '  Envelope controls: \'a\' Attack | \'d\' Decay | \'s\' Sustain | \'r\' Release | \'w\' Width | ↑↓ to adjust when active'
                        stdscr.addstr(row, 0, help_text)
            
            row += 1
            charts_start_row = row
            chart_idx = 0
            for col_idx in range(charts_per_row):
                current_row = charts_start_row
                for row_idx in range(charts_per_column):
                    if chart_idx >= len(all_charts):
                        break
                    chart_name, history_key = all_charts[chart_idx]
                    col_offset = col_idx * CHART_WIDTH_WITH_BORDERS
                    if current_row + CHART_TOTAL_HEIGHT > term_height - FOOTER_LINES:
                        break
                    
                    header = f'─── {chart_name} ' + '─' * (47 - len(chart_name))
                    try:
                        stdscr.addstr(current_row, col_offset, '  ' + header)
                        current_row += 1
                    except curses.error:
                        pass
                    
                    for line in make_chart(app.history[history_key], height=FIXED_CHART_HEIGHT, width=CHART_WIDTH):
                        if current_row < term_height - FOOTER_LINES:
                            try:
                                stdscr.addstr(current_row, col_offset, f'  │{line}│')
                                current_row += 1
                            except curses.error:
                                pass
                        else:
                            break
                    chart_idx += 1
                if chart_idx >= len(all_charts):
                    break
        else:
            FIXED_CHART_HEIGHT = 5
            CHART_WIDTH_WITH_BORDERS = 54
            CHART_HEADER_HEIGHT = 1
            CHART_TOTAL_HEIGHT = FIXED_CHART_HEIGHT + CHART_HEADER_HEIGHT
            fixed_lines = 12
            remaining_for_charts = content_height - fixed_lines
            charts_per_column = max(1, remaining_for_charts // CHART_TOTAL_HEIGHT)
            charts_per_row = max(1, term_width // CHART_WIDTH_WITH_BORDERS)
            standard_charts = [
                ('BEAT PULSE', 'beat_pulse'),
                ('BEAT PHASE', 'beat_phase'),
                ('BASS', 'bass'),
                ('MID', 'mid'),
                ('HIGH', 'high'),
                ('RMS', 'rms'),
                ('PEAK', 'peak')
            ]
            
            norm_rms = app.uniforms['u_audio_rms']
            norm_bass = app.uniforms['u_audio_bass']
            norm_mid = app.uniforms['u_audio_mid']
            norm_high = app.uniforms['u_audio_high']
            peak = app.uniforms['u_audio_peak']
            
            stdscr.addstr(row, 0, f'  RMS:  {make_bar(norm_rms, 48)} {norm_rms:.2f}')
            row += 1
            stdscr.addstr(row, 0, f'  Peak: {make_bar(peak, 48)} {peak:.4f}')
            row += 2
            stdscr.addstr(row, 0, '  FREQUENCY BANDS:                                               ')
            row += 1
            stdscr.addstr(row, 0, f"  Bass  (20-250Hz):  {make_bar(norm_bass, 35, '▓')} {norm_bass:.2f}")
            row += 1
            stdscr.addstr(row, 0, f"  Mids  (250-2kHz):  {make_bar(norm_mid, 35, '▒')} {norm_mid:.2f}")
            row += 1
            stdscr.addstr(row, 0, f"  Highs (2k-16kHz):  {make_bar(norm_high, 35, '░')} {norm_high:.2f}")
            row += 2
            
            output_status = 'ON ' if tempo_tracker.beat_output_enabled else 'OFF'
            tap_weight = tempo_tracker.get_tap_weight()
            
            stdscr.addstr(row, 0, '  ╔════════════════════════════════════════════════════════════╗')
            row += 1
            tempo_line = f'TEMPO [Output: {output_status}]'
            stdscr.addstr(row, 0, f'  ║  {tempo_line:<58}║')
            row += 1
            stdscr.addstr(row, 0, '  ╠════════════════════════════════════════════════════════════╣')
            row += 1
            
            conf_bar = make_bar(confidence, 12)
            bpm_line = f'BPM: {bpm:6.1f}  Confidence: {conf_bar} {confidence:.0%}'
            stdscr.addstr(row, 0, f'  ║  {bpm_line:<58}║')
            row += 1
            
            align_bar = make_bar(tempo_tracker.alignment_score, 12)
            align_line = f'Align: {align_bar} {tempo_tracker.alignment_score:.0%}  Taps: {len(tempo_tracker.tap_times)} (wt: {tap_weight:.1f})'
            stdscr.addstr(row, 0, f'  ║  {align_line:<58}║')
            row += 1
            
            phase_ind = make_phase_indicator(phase, 42)
            phase_line = f'Phase: [{phase_ind}]'
            stdscr.addstr(row, 0, f'  ║  {phase_line:<58}║')
            row += 1
            
            if not tempo_tracker.beat_output_enabled:
                beat_str = '⏸ OFF'
            elif is_beat:
                beat_str = '● BEAT!'
            else:
                beat_str = '○      '
            
            onset_str = '⚡' if tempo_tracker.current_onset else ' '
            beat_line = f'Beat: {beat_str} {onset_str} Onset   Count: {tempo_tracker.beat_count:<6}'
            stdscr.addstr(row, 0, f'  ║  {beat_line:<58}║')
            row += 1
            stdscr.addstr(row, 0, '  ╚════════════════════════════════════════════════════════════╝')
            row += 2
            
            charts_start_row = row
            chart_idx = 0
            for col_idx in range(charts_per_row):
                current_row = charts_start_row
                for row_idx in range(charts_per_column):
                    if chart_idx >= len(standard_charts):
                        break
                    chart_name, history_key = standard_charts[chart_idx]
                    col_offset = col_idx * CHART_WIDTH_WITH_BORDERS
                    if current_row + CHART_TOTAL_HEIGHT > term_height - FOOTER_LINES:
                        break
                    
                    header = f'─── {chart_name} ' + '─' * (47 - len(chart_name))
                    try:
                        stdscr.addstr(current_row, col_offset, '  ' + header)
                        current_row += 1
                    except curses.error:
                        pass
                    
                    for line in make_chart(app.history[history_key], height=FIXED_CHART_HEIGHT, width=CHART_WIDTH):
                        if current_row < term_height - FOOTER_LINES:
                            try:
                                stdscr.addstr(current_row, col_offset, f'  │{line}│')
                                current_row += 1
                            except curses.error:
                                pass
                        else:
                            break
                    chart_idx += 1
                if chart_idx >= len(standard_charts):
                    break
        
        footer_row = term_height - 2
        stdscr.addstr(footer_row, 0, '════════════════════════════════════════════════════════════════')
        if app.show_uniforms:
            footer_text = '  ↑↓ navigate | \'n\' norm/raw | \'g\' gate | \'p\' envelope | \'u\' hide | \'q\' quit'
            stdscr.addstr(footer_row + 1, 0, f'{footer_text:<64}')
        else:
            footer_text = '  \'b\' tap | \'B\' toggle | \'r\' reset | \'u\' uniforms | \'q\' quit'
            stdscr.addstr(footer_row + 1, 0, f'{footer_text:<64}')
        
        stdscr.refresh()
    
    return draw_ui
