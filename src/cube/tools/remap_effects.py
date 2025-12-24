"""
Curses-based effect remapping tool with MIDI learn functionality.

Allows users to remap effects to MIDI pads and keyboard keys, with support for
presets and additive bindings.
"""

import curses
import sys
import time
from pathlib import Path
from typing import List, Optional, Union, Tuple, Dict
from queue import Queue
import threading

# Try to import MIDI support
try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False

from cube.input.actions import Action
from cube.render.effect_config_loader import load_effect_config
from cube.input.effect_bindings_loader import (
    load_effect_bindings, save_effect_bindings, load_preset, save_preset,
    list_presets, delete_preset, EffectBinding
)
from cube.midi.config_loader import load_midi_config


class RemappingUI:
    """Curses-based remapping UI."""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.learn_mode_flag = self.project_root / '.learn_mode'
        
        # Load effects and bindings
        self.effects = load_effect_config()
        if not self.effects:
            # Show error message
            try:
                self.stdscr.addstr(0, 0, "Error: No effects loaded from effects_config.yml")
                self.stdscr.addstr(1, 0, "Press any key to exit...")
                self.stdscr.refresh()
                self.stdscr.getch()
            except:
                pass
            raise Exception("No effects loaded from effects_config.yml")
        
        self.preset_name, self.bindings = load_effect_bindings()
        self.binding_map: Dict[Action, EffectBinding] = {
            b.action: b for b in self.bindings
        }
        
        # Sort effects: bound first (by key value), then unbound (alphabetically)
        self._sort_effects()
        
        # UI state
        self.selected_index = 0
        self.scroll_offset = 0
        self.mode = 'normal'  # 'normal', 'learn', 'save_preset', 'load_preset', 'delete_preset'
        self.message = ""
        self.message_time = 0
        
        # MIDI state
        self.midi_in = None
        self.midi_queue = Queue()
        self.midi_connected = False
        self._setup_midi()
        
        
    def _setup_midi(self):
        """Setup MIDI connection for learn mode."""
        if not RTMIDI_AVAILABLE:
            return
            
        try:
            midi_config = load_midi_config()
            if not midi_config:
                return
                
            self.midi_in = rtmidi.MidiIn()
            available_ports = self.midi_in.get_ports()
            
            if not available_ports:
                return
                
            # Find device
            port_index = None
            if midi_config.device_name == "auto":
                port_index = 0
            else:
                for i, port_name in enumerate(available_ports):
                    if midi_config.device_name.lower() in port_name.lower():
                        port_index = i
                        break
                        
            if port_index is None:
                return
                
            self.midi_in.open_port(port_index)
            self.midi_in.set_callback(self._midi_callback)
            self.midi_connected = True
        except Exception as e:
            # MIDI not available, continue with keyboard-only
            pass
            
    def _midi_callback(self, message, data):
        """MIDI callback for learn mode."""
        midi_message, delta_time = message
        if len(midi_message) >= 3:
            status = midi_message[0] & 0xF0
            note = midi_message[1]
            velocity = midi_message[2] if len(midi_message) > 2 else 0
            
            # Note on (0x90) or note off (0x80)
            if status in (0x90, 0x80):
                # Only capture note on with velocity > 0
                if status == 0x90 and velocity > 0:
                    # Notes 36-51 are pads 1-16
                    if 36 <= note <= 51:
                        self.midi_queue.put(note)
                        
    def _get_binding_sort_key(self, effect) -> tuple:
        """
        Get sort key for an effect.
        Returns (is_bound, key_value, effect_name) where:
        - is_bound: 0 for bound, 1 for unbound (so bound comes first)
        - key_value: numeric key value (1-8 for regular, 9-16 for shift+1-8)
        - effect_name: for alphabetical sorting of unbound
        """
        if effect.action not in self.binding_map:
            # Unbound: sort alphabetically
            return (1, 999, effect.action.name)
        
        binding = self.binding_map[effect.action]
        if not binding.inputs:
            # No bindings: treat as unbound
            return (1, 999, effect.action.name)
        
        # Get the first binding (primary key for sorting)
        first_input = binding.inputs[0]
        
        # Parse key value
        if isinstance(first_input, tuple):
            # Shift modifier: ('key:shift', 'key:1')
            if len(first_input) == 2 and first_input[0] == 'key:shift':
                key_str = first_input[1]
                if key_str.startswith('key:'):
                    try:
                        key_num = int(key_str[4:])
                        # Shift keys: 9-16 (shift+1 through shift+8)
                        return (0, 8 + key_num, effect.action.name)
                    except ValueError:
                        pass
        elif isinstance(first_input, str):
            # Regular key: 'key:1' or 'midi:note_36'
            if first_input.startswith('key:'):
                try:
                    key_num = int(first_input[4:])
                    # Regular keys: 1-8
                    return (0, key_num, effect.action.name)
                except ValueError:
                    pass
            elif first_input.startswith('midi:note_'):
                try:
                    note_num = int(first_input[11:])
                    # MIDI notes: 36-51 map to 1-16, but we'll use note number directly
                    # For sorting, we want MIDI to come after keyboard
                    return (0, 100 + note_num, effect.action.name)
                except ValueError:
                    pass
        
        # Fallback: bound but couldn't parse, sort by name
        return (0, 999, effect.action.name)
    
    def _sort_effects(self):
        """Sort effects: bound first (by key value), then unbound (alphabetically)."""
        self.effects.sort(key=self._get_binding_sort_key)
    
    def _format_input(self, inp: Union[str, Tuple[str, ...]]) -> str:
        """Format input for display."""
        if isinstance(inp, tuple):
            if len(inp) == 2 and inp[0] == 'key:shift':
                key_num = inp[1].replace('key:', '')
                return f"Shift+{key_num}"
            return '+'.join(inp)
        elif isinstance(inp, str):
            if inp.startswith('midi:note_'):
                note_num = int(inp.replace('midi:note_', ''))
                pad_num = note_num - 35  # Note 36 = pad 1
                return f"MIDI Pad {pad_num}"
            elif inp.startswith('key:'):
                return inp.replace('key:', 'Key ')
        return str(inp)
        
    def _format_input_for_save(self, inp: Union[str, Tuple[str, ...]]) -> Union[str, Tuple[str, ...]]:
        """Format input for saving (normalize format)."""
        if isinstance(inp, tuple):
            return tuple(str(x) for x in inp)
        return str(inp)
        
    def _save_bindings(self):
        """Save current bindings to file."""
        bindings_list = list(self.binding_map.values())
        save_effect_bindings(bindings_list, self.preset_name)
        self._show_message("Bindings saved")
        
    def _show_message(self, msg: str):
        """Show a temporary message."""
        self.message = msg
        self.message_time = time.time()
        
    def _enter_learn_mode(self):
        """Enter learn mode for selected effect."""
        if self.selected_index >= len(self.effects):
            return
            
        effect = self.effects[self.selected_index]
        self.mode = 'learn'
        
        # Create learn mode flag
        try:
            self.learn_mode_flag.touch()
        except Exception:
            pass
            
        self._show_message(f"Learning for {effect.action.name.replace('TOGGLE_', '')}... Press MIDI pad or key (ESC to cancel)")
        
    def _exit_learn_mode(self):
        """Exit learn mode."""
        self.mode = 'normal'
        # Remove learn mode flag
        try:
            if self.learn_mode_flag.exists():
                self.learn_mode_flag.unlink()
        except Exception:
            pass
            
    def _learn_input(self) -> Optional[Union[str, Tuple[str, ...]]]:
        """Capture input in learn mode. Returns input string/tuple or None if cancelled."""
        start_time = time.time()
        timeout = 30.0  # 30 second timeout
        
        while time.time() - start_time < timeout:
            # Check for MIDI input
            try:
                note = self.midi_queue.get_nowait()
                self._exit_learn_mode()
                return f'midi:note_{note}'
            except:
                pass
                
            # Check for keyboard input
            self.stdscr.nodelay(True)
            key = self.stdscr.getch()
            
            if key == -1:
                time.sleep(0.01)
                continue
                
            # ESC cancels
            if key == 27:  # ESC
                self._exit_learn_mode()
                return None
            
            # In curses, shift+number produces the shifted character
            # Shift+1 = '!', Shift+2 = '@', Shift+3 = '#', etc.
            shift_number_map = {
                ord('!'): '1',
                ord('@'): '2',
                ord('#'): '3',
                ord('$'): '4',
                ord('%'): '5',
                ord('^'): '6',
                ord('&'): '7',
                ord('*'): '8',
            }
            
            # Check for shift+number combinations
            if key in shift_number_map:
                key_num = shift_number_map[key]
                self._exit_learn_mode()
                return ('key:shift', f'key:{key_num}')
            
            # Regular keys 1-8
            if ord('1') <= key <= ord('8'):
                key_num = chr(key)
                self._exit_learn_mode()
                return f'key:{key_num}'
            
        # Timeout
        self._exit_learn_mode()
        return None
        
    def _add_binding(self, effect: Action, inp: Union[str, Tuple[str, ...]]):
        """Add a binding to an effect (additive)."""
        if effect not in self.binding_map:
            self.binding_map[effect] = EffectBinding(effect, [])
            
        binding = self.binding_map[effect]
        
        # Check for duplicates
        normalized = self._format_input_for_save(inp)
        if normalized in binding.inputs:
            self._show_message("Binding already exists!")
            return
            
        binding.inputs.append(normalized)
        self._save_bindings()
        self._sort_effects()
        # Adjust selected_index to keep the same effect selected
        old_action = effect
        for i, ef in enumerate(self.effects):
            if ef.action == old_action:
                self.selected_index = i
                break
        self._show_message(f"Added binding: {self._format_input(inp)}")
        
    def _clear_bindings(self, effect: Action):
        """Clear all bindings for an effect."""
        if effect in self.binding_map:
            del self.binding_map[effect]
            self._save_bindings()
            self._sort_effects()
            # Adjust selected_index to keep the same effect selected
            for i, ef in enumerate(self.effects):
                if ef.action == effect:
                    self.selected_index = i
                    break
            self._show_message("All bindings cleared")
        else:
            self._show_message("No bindings to clear")
    
    def _upload_bindings(self):
        """Force reload bindings in visualization by saving and touching the config file."""
        try:
            # First ensure bindings are saved
            self._save_bindings()
            
            config_path = self.project_root / 'effect_bindings.yml'
            if config_path.exists():
                # Get current mtime, wait a bit, then set to a time that's definitely different
                import os
                import time
                current_mtime = config_path.stat().st_mtime
                time.sleep(0.11)  # Wait slightly longer than the check interval (0.5s / 5 = 0.1s, but be safe)
                # Set mtime to current time (which will be > current_mtime + 0.1)
                new_time = time.time()
                os.utime(config_path, (new_time, new_time))
                self._show_message("Bindings uploaded to visualization")
            else:
                self._show_message("No bindings file to upload")
        except Exception as e:
            self._show_message(f"Upload failed: {e}")
            
    def _save_preset_dialog(self):
        """Show save preset dialog."""
        self.mode = 'save_preset'
        self.preset_name_input = ""
        self._show_message("Enter preset name (Enter to save, ESC to cancel): ")
        
    def _load_preset_dialog(self):
        """Show load preset dialog."""
        presets = list_presets()
        if not presets:
            self._show_message("No presets found")
            return
            
        self.mode = 'load_preset'
        self.preset_list = presets
        self.preset_selected = 0
        
    def _delete_preset_dialog(self):
        """Show delete preset dialog."""
        presets = list_presets()
        if not presets:
            self._show_message("No presets found")
            return
            
        self.mode = 'delete_preset'
        self.preset_list = presets
        self.preset_selected = 0
        
    def _render(self):
        """Render the UI."""
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Header
        preset_display = self.preset_name if self.preset_name else "Unsaved"
        header = f"Effect Remapping - Preset: {preset_display}"
        if self.message and time.time() - self.message_time < 3.0:
            header += f" | {self.message}"
        try:
            self.stdscr.addstr(0, 0, header[:width-1], curses.A_BOLD)
        except:
            pass
            
        # Instructions
        instructions = "↑↓: Navigate | Enter: Learn | d: Delete binding | u: Upload | s: Save preset | l: Load preset | n: New preset | q: Quit"
        try:
            self.stdscr.addstr(1, 0, instructions[:width-1])
        except:
            pass
            
        # Effects list
        start_y = 3
        visible_height = height - start_y - 1
        
        for i in range(self.scroll_offset, min(len(self.effects), self.scroll_offset + visible_height)):
            effect = self.effects[i]
            y = start_y + (i - self.scroll_offset)
            
            if y >= height - 1:
                break
                
            # Effect name
            effect_name = effect.action.name.replace('TOGGLE_', '')
            is_selected = (i == self.selected_index and self.mode == 'normal')
            
            # Get bindings for this effect
            bindings_str = ""
            if effect.action in self.binding_map:
                binding = self.binding_map[effect.action]
                bindings_str = ", ".join([self._format_input(inp) for inp in binding.inputs])
            else:
                bindings_str = "(no bindings)"
                
            line = f"{'>>' if is_selected else '  '} {effect_name:30} | {bindings_str}"
            
            attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
            try:
                self.stdscr.addstr(y, 0, line[:width-1], attr)
            except:
                pass
                
        # Preset dialogs
        if self.mode == 'load_preset' or self.mode == 'delete_preset':
            # Show preset list
            dialog_y = height // 2 - len(self.preset_list) // 2
            dialog_x = width // 2 - 20
            
            title = "Load Preset" if self.mode == 'load_preset' else "Delete Preset"
            try:
                self.stdscr.addstr(dialog_y - 1, dialog_x, title)
                for i, preset in enumerate(self.preset_list):
                    attr = curses.A_REVERSE if i == self.preset_selected else curses.A_NORMAL
                    self.stdscr.addstr(dialog_y + i, dialog_x, f"{'>>' if i == self.preset_selected else '  '} {preset}", attr)
            except:
                pass
        elif self.mode == 'save_preset':
            # Show input dialog
            dialog_y = height // 2
            dialog_x = width // 2 - 20
            try:
                self.stdscr.addstr(dialog_y, dialog_x, "Preset name: " + self.preset_name_input + "_")
            except:
                pass
                
        self.stdscr.refresh()
        
    def _handle_input(self, key: int) -> bool:
        """Handle user input. Returns True if should continue, False if should quit."""
        if self.mode == 'learn':
            # Learn mode handled separately
            return True
            
        if self.mode == 'save_preset':
            if key == 27:  # ESC
                self.mode = 'normal'
                self.message = ""
                self.preset_name_input = ""
                return True
            elif key == ord('\n') or key == ord('\r'):
                # Save preset
                if self.preset_name_input.strip():
                    preset_name = self.preset_name_input.strip()
                    bindings_list = list(self.binding_map.values())
                    if save_preset(bindings_list, preset_name):
                        self.preset_name = preset_name
                        self._save_bindings()
                        self._show_message(f"Saved preset: {preset_name}")
                    else:
                        self._show_message("Failed to save preset")
                self.mode = 'normal'
                self.preset_name_input = ""
                return True
            elif key == curses.KEY_BACKSPACE or key == 127:
                # Backspace
                if self.preset_name_input:
                    self.preset_name_input = self.preset_name_input[:-1]
            elif 32 <= key <= 126:  # Printable ASCII
                self.preset_name_input += chr(key)
            return True
            
        if self.mode == 'load_preset':
            if key == 27:  # ESC
                self.mode = 'normal'
                return True
            elif key == curses.KEY_UP:
                self.preset_selected = max(0, self.preset_selected - 1)
                return True
            elif key == curses.KEY_DOWN:
                self.preset_selected = min(len(self.preset_list) - 1, self.preset_selected + 1)
                return True
            elif key == ord('\n') or key == ord('\r'):
                # Load preset
                preset_name = self.preset_list[self.preset_selected]
                bindings = load_preset(preset_name)
                self.binding_map = {b.action: b for b in bindings}
                self.preset_name = preset_name
                self._save_bindings()
                self._sort_effects()
                self.selected_index = 0  # Reset to top after loading
                self.mode = 'normal'
                self._show_message(f"Loaded preset: {preset_name}")
                return True
            return True
            
        if self.mode == 'delete_preset':
            if key == 27:  # ESC
                self.mode = 'normal'
                return True
            elif key == curses.KEY_UP:
                self.preset_selected = max(0, self.preset_selected - 1)
                return True
            elif key == curses.KEY_DOWN:
                self.preset_selected = min(len(self.preset_list) - 1, self.preset_selected + 1)
                return True
            elif key == ord('\n') or key == ord('\r'):
                # Delete preset
                preset_name = self.preset_list[self.preset_selected]
                if delete_preset(preset_name):
                    self._show_message(f"Deleted preset: {preset_name}")
                self.mode = 'normal'
                return True
            return True
            
        # Normal mode
        if key == ord('q') or key == ord('Q'):
            return False
        elif key == curses.KEY_UP:
            self.selected_index = max(0, self.selected_index - 1)
            if self.selected_index < self.scroll_offset:
                self.scroll_offset = self.selected_index
        elif key == curses.KEY_DOWN:
            self.selected_index = min(len(self.effects) - 1, self.selected_index + 1)
            if self.selected_index >= self.scroll_offset + (self.stdscr.getmaxyx()[0] - 4):
                self.scroll_offset = self.selected_index - (self.stdscr.getmaxyx()[0] - 5)
        elif key == ord('\n') or key == ord('\r'):
            self._enter_learn_mode()
        elif key == ord('s') or key == ord('S'):
            self._save_preset_dialog()
        elif key == ord('l') or key == ord('L'):
            self._load_preset_dialog()
        elif key == ord('n') or key == ord('N'):
            # New preset (clear bindings)
            self.binding_map = {}
            self.preset_name = None
            self._save_bindings()
            self._sort_effects()
            self.selected_index = 0  # Reset to top
            self._show_message("New preset started")
        elif key == ord('d') or key == ord('D'):
            # Clear all bindings for selected effect
            effect = self.effects[self.selected_index]
            self._clear_bindings(effect.action)
        elif key == ord('u') or key == ord('U'):
            # Upload/force reload bindings in visualization
            self._upload_bindings()
            
        return True
        
    def run(self):
        """Main run loop."""
        # curses.wrapper() already initializes curses, but we need to configure our window
        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        
        try:
            while True:
                self._render()
                
                if self.mode == 'learn':
                    inp = self._learn_input()
                    if inp is not None:
                        effect = self.effects[self.selected_index]
                        self._add_binding(effect.action, inp)
                    time.sleep(0.05)
                else:
                    key = self.stdscr.getch()
                    if key != -1:
                        if not self._handle_input(key):
                            break
                    time.sleep(0.05)
                    
        except KeyboardInterrupt:
            pass
        finally:
            # Cleanup (curses.wrapper() will call endwin() automatically)
            self._exit_learn_mode()
            if self.midi_in:
                try:
                    self.midi_in.close_port()
                except:
                    pass
            # Don't call curses.endwin() here - curses.wrapper() handles it


def _run_ui(stdscr):
    """Wrapper function for curses.wrapper()."""
    ui = RemappingUI(stdscr)
    ui.run()


def main():
    """Main entry point."""
    import sys
    
    try:
        curses.wrapper(_run_ui)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Print error - try to restore terminal first
        try:
            curses.endwin()
        except:
            pass
        sys.stderr.write(f"Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

