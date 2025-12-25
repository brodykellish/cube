"""
Thread-safe debug log capture for multi-threaded applications.

Captures stdout from all threads and stores logs with thread identification.
"""
import sys
import threading
from datetime import datetime
from typing import List


class StdoutCapture:
    """Thread-safe stdout capture with thread identification."""
    
    def __init__(self, log_lines: List[str], log_lock: threading.Lock):
        """
        Initialize stdout capture.
        
        Args:
            log_lines: Shared list to store log lines
            log_lock: Lock to protect log_lines from concurrent access
        """
        self.log_lines = log_lines
        self.log_lock = log_lock
        self.original_stdout = sys.stdout
        self.buffer = ""  # Buffer for partial lines
    
    def write(self, text: str):
        """Thread-safe write with thread identification and timestamp."""
        if not text:
            return
        
        if not isinstance(text, str):
            text = str(text)
        
        # Get thread identifier
        thread_name = threading.current_thread().name
        if thread_name == "MainThread":
            prefix = "[MAIN]"
        elif thread_name == "VisualizationThread":
            prefix = "[VIZ]"
        else:
            prefix = f"[{thread_name}]"
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with self.log_lock:
            self.buffer += text
            
            # Process complete lines
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.rstrip('\r\n')
                if line:  # Only add non-empty lines
                    formatted = f"[{timestamp}] {prefix} {line}"
                    self.log_lines.append(formatted)
                    # Keep last 1000 lines
                    if len(self.log_lines) > 1000:
                        self.log_lines.pop(0)
        
        # Also write to original stdout (for terminal/debugging)
        self.original_stdout.write(text)
    
    def flush(self):
        """Flush buffer if it has content."""
        with self.log_lock:
            if self.buffer.strip():
                thread_name = threading.current_thread().name
                if thread_name == "MainThread":
                    prefix = "[MAIN]"
                elif thread_name == "VisualizationThread":
                    prefix = "[VIZ]"
                else:
                    prefix = f"[{thread_name}]"
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                line = self.buffer.rstrip('\r\n')
                if line:
                    formatted = f"[{timestamp}] {prefix} {line}"
                    self.log_lines.append(formatted)
                    if len(self.log_lines) > 1000:
                        self.log_lines.pop(0)
                self.buffer = ""
        
        self.original_stdout.flush()
    
    def isatty(self):
        return False
    
    def writable(self):
        return True

