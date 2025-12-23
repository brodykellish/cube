"""
Modular debug log viewer for curses.

Can be rendered in any curses window/subwindow.
"""

import curses
import sys
import threading
from typing import List, Optional
from io import StringIO


class StdoutCapture:
    """Capture stdout and store lines in a list."""
    
    def __init__(self, log_lines: List[str], lock: threading.Lock):
        self.log_lines = log_lines
        self.lock = lock
        self.original_stdout = sys.stdout
        self.buffer = ""
    
    def write(self, text: str):
        """Write text to buffer and process complete lines."""
        if not text:
            return
        
        if not isinstance(text, str):
            text = str(text)
        
        with self.lock:
            self.buffer += text
            
            # Process complete lines
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.rstrip('\r\n')
                if line:  # Only add non-empty lines
                    self.log_lines.append(line)
                    # Keep last 1000 lines
                    if len(self.log_lines) > 1000:
                        self.log_lines.pop(0)
    
    def flush(self):
        """Flush buffer if it has content."""
        with self.lock:
            if self.buffer.strip():
                line = self.buffer.rstrip('\r\n')
                if line:
                    self.log_lines.append(line)
                    if len(self.log_lines) > 1000:
                        self.log_lines.pop(0)
                self.buffer = ""
    
    def isatty(self):
        return False
    
    def writable(self):
        return True


class DebugLogView:
    """
    Modular debug log viewer that can be rendered in any curses window.
    
    Captures stdout and displays it with navigation and expansion.
    """
    
    def __init__(self, window, log_lines: Optional[List[str]] = None, log_lock: Optional[threading.Lock] = None, stdout_capture: Optional[StdoutCapture] = None):
        """
        Initialize debug log viewer.
        
        Args:
            window: Curses window/subwindow to render in
            log_lines: Optional shared list for log lines (if None, creates new one)
            log_lock: Optional shared lock for log_lines (if None, creates new one)
            stdout_capture: Optional existing stdout capture (if None, won't capture)
        """
        self.window = window
        
        # Use provided log storage or create new
        if log_lines is not None and log_lock is not None:
            self.log_lines = log_lines
            self.log_lock = log_lock
            self.owns_log_storage = False
        else:
            self.log_lines: List[str] = []
            self.log_lock = threading.Lock()
            self.owns_log_storage = True
        
        self.stdout_capture = stdout_capture
        
        # UI state
        self.selected_index = 0
        self.expanded_index: Optional[int] = None
        self.scroll_offset = 0
        self.last_log_count = 0
        self.auto_scroll = True
        self.initial_logs_loaded = False
    
    def cleanup(self):
        """Cleanup (no-op if using shared storage)."""
        # Don't restore stdout here - it's managed externally
        pass
    
    def render(self):
        """Render the debug log view in the window."""
        try:
            height, width = self.window.getmaxyx()
        except curses.error:
            return
        
        # Calculate available space
        header_height = 1
        footer_height = 1
        content_height = height - header_height - footer_height
        
        if content_height < 1:
            return
        
        # Get current log lines
        with self.log_lock:
            current_logs = list(self.log_lines)
            current_log_count = len(current_logs)
        
        # Initialize on first load
        if not self.initial_logs_loaded and current_log_count > 0:
            self.selected_index = current_log_count - 1
            self.last_log_count = current_log_count
            self.initial_logs_loaded = True
            self.auto_scroll = True
        
        # Check if new lines were added
        if current_log_count > self.last_log_count:
            if self.auto_scroll:
                self.selected_index = current_log_count - 1
            elif self.selected_index == self.last_log_count - 1:
                self.selected_index = current_log_count - 1
                self.auto_scroll = True
            self.last_log_count = current_log_count
        
        if not current_logs:
            self.window.clear()
            try:
                self.window.addstr(0, 0, "Waiting for log messages...")
            except curses.error:
                pass
            return
        
        # Calculate expanded line wrapping
        expanded_line_wrapped = []
        if self.expanded_index is not None and self.expanded_index < len(current_logs):
            expanded_line = current_logs[self.expanded_index]
            max_width = width - 3
            
            # Word wrap
            words = expanded_line.split(' ')
            current_wrapped_line = ""
            for word in words:
                if len(current_wrapped_line) + len(word) + 1 <= max_width:
                    current_wrapped_line += word + " "
                else:
                    if current_wrapped_line:
                        expanded_line_wrapped.append(current_wrapped_line.rstrip())
                    current_wrapped_line = word + " "
            if current_wrapped_line:
                expanded_line_wrapped.append(current_wrapped_line.rstrip())
        
        expanded_height = len(expanded_line_wrapped) if self.expanded_index is not None else 0
        
        # Adjust scroll for expanded line
        if self.expanded_index is not None:
            if self.expanded_index < self.scroll_offset:
                self.scroll_offset = self.expanded_index
            elif self.expanded_index >= self.scroll_offset + content_height - expanded_height:
                self.scroll_offset = self.expanded_index - (content_height - expanded_height) + 1
        
        num_logs = len(current_logs)
        
        # Adjust selected_index if needed
        if self.selected_index >= num_logs:
            self.selected_index = max(0, num_logs - 1)
        if self.selected_index < 0:
            self.selected_index = 0
        
        # Calculate scroll offset
        available_height = content_height - expanded_height if self.expanded_index is not None else content_height
        
        if self.auto_scroll:
            self.scroll_offset = max(0, num_logs - available_height)
        else:
            if self.selected_index < self.scroll_offset:
                self.scroll_offset = self.selected_index
            elif self.selected_index >= self.scroll_offset + available_height:
                self.scroll_offset = self.selected_index - available_height + 1
        
        self.window.clear()
        
        # Header
        try:
            scroll_indicator = " [AUTO-SCROLL]" if self.auto_scroll else ""
            header_text = f" Debug Log ({num_logs} lines){scroll_indicator} "
            self.window.addstr(0, 0, header_text[:width-1], curses.color_pair(1) if curses.has_colors() else 0)
        except curses.error:
            pass
        
        # Display log lines with in-place expansion
        y = header_height
        max_y = height - footer_height
        
        display_start = max(0, self.scroll_offset)
        display_end = min(num_logs, self.scroll_offset + available_height)
        
        for i in range(display_start, display_end):
            log_index = i
            
            if y >= max_y:
                break
            
            # Check if this is the expanded line
            if log_index == self.expanded_index:
                # Show expanded line content
                for wrapped_line in expanded_line_wrapped:
                    if y >= max_y:
                        break
                    try:
                        self.window.addstr(y, 0, ">", curses.color_pair(3) if curses.has_colors() else 0)
                        self.window.addstr(y, 2, wrapped_line[:width - 3], curses.color_pair(4) if curses.has_colors() else 0)
                    except curses.error:
                        pass
                    y += 1
                continue
            
            # Regular log line
            line = current_logs[log_index]
            preview = line[:100]
            if len(line) > 100:
                preview += "..."
            display_line = preview[:width - 3]
            
            # Highlight selected line
            try:
                if log_index == self.selected_index:
                    self.window.addstr(y, 0, ">", curses.color_pair(3) if curses.has_colors() else 0)
                    self.window.addstr(y, 1, display_line, curses.color_pair(4) if curses.has_colors() else 0)
                else:
                    self.window.addstr(y, 1, display_line)
            except curses.error:
                pass
            
            y += 1
        
        # Footer
        footer_y = height - 1
        if footer_y >= 0 and num_logs > 0:
            try:
                footer_text = f" Line {self.selected_index + 1}/{num_logs} - {len(current_logs[self.selected_index])} chars "
                self.window.addstr(footer_y, 0, footer_text[:width-1], curses.color_pair(2) if curses.has_colors() else 0)
            except curses.error:
                pass
    
    def handle_input(self, key: int) -> bool:
        """
        Handle keyboard input.
        
        Args:
            key: Key code from getch()
            
        Returns:
            True if input was handled, False otherwise
        """
        with self.log_lock:
            num_logs = len(self.log_lines)
        
        if key == curses.KEY_UP:
            if self.expanded_index is not None:
                self.expanded_index = None
            elif self.selected_index > 0:
                self.selected_index -= 1
                self.auto_scroll = False
            return True
        elif key == curses.KEY_DOWN:
            if self.expanded_index is not None:
                self.expanded_index = None
            elif self.selected_index < num_logs - 1:
                self.selected_index += 1
                if self.selected_index == num_logs - 1:
                    self.auto_scroll = True
                else:
                    self.auto_scroll = False
            return True
        elif key == ord('\n') or key == ord('\r'):  # ENTER
            if self.expanded_index is not None:
                self.expanded_index = None
            elif num_logs > 0 and self.selected_index < num_logs:
                self.expanded_index = self.selected_index
            return True
        elif key == ord('q') or key == 27:  # 'q' or ESC
            return False  # Signal to quit (if needed)
        
        return False  # Input not handled

