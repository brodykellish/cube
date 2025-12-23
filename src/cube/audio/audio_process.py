"""Audio process launcher and manager."""
import subprocess
import sys
import os
import platform
import signal
import time
from pathlib import Path


class AudioProcessManager:
    """Manages the audio analysis subprocess in a new terminal window."""

    def __init__(self):
        self.process = None
        self._pid_file = Path('/tmp/cube_audio_process.pid')

    def _get_python_path(self):
        """Get the current Python interpreter path."""
        return sys.executable

    def _get_project_root(self):
        """Get the project root directory (where src/ is located)."""
        return Path(__file__).parent.parent.parent.parent

    def _launch_macos(self, python_path: str, project_root: Path):
        """Launch audio process in a new Terminal window on macOS."""
        applescript = f'''
        tell application "Terminal"
            do script "cd {project_root} && echo $$ > {self._pid_file} && {python_path} -m cube.audio.audio_input; exit"
            activate
        end tell
        '''
        subprocess.Popen(['osascript', '-e', applescript], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print('[AudioProcess] Launched in new Terminal window (macOS)')
        print(f'[AudioProcess] PID will be written to: {self._pid_file}')

    def _launch_linux(self, python_path: str, project_root: Path):
        """Launch audio process in a new terminal window on Linux."""
        terminals = [
            ['gnome-terminal', '--', 'bash', '-c'],
            ['konsole', '-e', 'bash', '-c'],
            ['xterm', '-e', 'bash', '-c'],
            ['x-terminal-emulator', '-e', 'bash', '-c']
        ]
        command = f'cd {project_root} && {python_path} -m cube.audio.audio_input; read -p \'Press Enter to close...\''
        for terminal_cmd in terminals:
            try:
                subprocess.Popen(terminal_cmd + [command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f'[AudioProcess] Launched in new terminal ({terminal_cmd[0]})')
                return
            except FileNotFoundError:
                continue
        print('[AudioProcess] WARNING: No suitable terminal emulator found')
        print('[AudioProcess] Please run manually: cd <project_root> && python -m cube.audio.audio_input')

    def start(self):
        """Start the audio process in a new terminal window."""
        if self.is_alive():
            return
        python_path = self._get_python_path()
        project_root = self._get_project_root()
        system = platform.system()
        if system == 'Darwin':
            self._launch_macos(python_path, project_root)
        elif system == 'Linux':
            self._launch_linux(python_path, project_root)
        else:
            print(f'[AudioProcess] WARNING: Unsupported platform: {system}')
            print(f'[AudioProcess] Please run manually: cd {project_root} && python -m cube.audio.audio_input')

    def stop(self):
        """Stop the audio process and close terminal window."""
        if not self._pid_file.exists():
            print('[AudioProcess] No PID file found, process may not be running')
            return
        
        try:
            with open(self._pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            print(f'[AudioProcess] Terminating audio process (PID: {pid})')
            
            try:
                os.kill(pid, signal.SIGTERM)
                print(f'[AudioProcess] Sent SIGTERM to PID {pid}')
                time.sleep(0.5)
                
                # Check if process is still running
                try:
                    os.kill(pid, 0)
                    print('[AudioProcess] Process still running, sending SIGKILL')
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
                
                self._pid_file.unlink()
                if platform.system() == 'Darwin':
                    self._close_macos_terminal_window()
                    
            except OSError as e:
                print(f'[AudioProcess] Process already terminated or not found: {e}')
                self._pid_file.unlink()
                
        except Exception as e:
            print(f'[AudioProcess] Error stopping process: {e}')

    def _close_macos_terminal_window(self):
        """Close Terminal windows running the audio process on macOS."""
        try:
            applescript = '''
            tell application "Terminal"
                set windowList to every window
                repeat with aWindow in windowList
                    set tabList to every tab of aWindow
                    repeat with aTab in tabList
                        if processes of aTab contains "python" then
                            set tabName to name of aTab
                            if tabName contains "cube.audio.audio_input" then
                                close aTab
                            end if
                        end if
                    end repeat
                end repeat
            end tell
            '''
            subprocess.run(['osascript', '-e', applescript], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
            print('[AudioProcess] Closed Terminal window')
        except Exception as e:
            print(f'[AudioProcess] Could not close Terminal window: {e}')

    def is_alive(self) -> bool:
        """
        Check if the audio process is running.
        Note: This is a best-effort check - we can't reliably track the process
        across terminal windows, so we assume it's running if recently started.
        """
        return False

    def restart(self):
        """Restart the audio process."""
        self.stop()
        self.start()
