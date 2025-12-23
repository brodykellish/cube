#!/usr/bin/env python3
"""
Test script for curses-based debug log viewer.

Captures stdout and displays it in a curses window with navigation.
"""

import curses
import sys
import threading
import time
from typing import List
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


def main(stdscr):
    """Main curses application."""
    # Initialize curses
    curses.curs_set(0)  # Hide cursor
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    
    # Enable colors if available
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Selected line
    
    # Shared log storage
    log_lines: List[str] = []
    log_lock = threading.Lock()
    
    # Redirect stdout
    original_stdout = sys.stdout
    stdout_capture = StdoutCapture(log_lines, log_lock)
    sys.stdout = stdout_capture
    
    # Start log generator thread
    running = threading.Event()
    running.set()
    
    def generate_logs():
        """Generate a log line every second."""
        counter = 0
        while running.is_set():
            counter += 1
            print(f"[{counter:04d}] Test log message at {time.strftime('%H:%M:%S')} - This is a sample log line that might be quite long and contain useful debugging information")
            time.sleep(1)
    
    log_thread = threading.Thread(target=generate_logs, daemon=True)
    log_thread.start()
    
    # UI state
    selected_index = 0
    expanded_index = None  # None means selection mode, otherwise index of expanded line
    scroll_offset = 0
    last_log_count = 0  # Track when new lines are added
    auto_scroll = True  # Auto-scroll to bottom when new lines arrive
    initial_logs_loaded = False
    
    try:
        while True:
            # Get screen dimensions
            height, width = stdscr.getmaxyx()
            
            # Calculate available space (leave room for header/footer)
            # Don't use the very last line (curses limitation)
            header_height = 2
            footer_height = 1
            content_height = height - header_height - footer_height - 1  # -1 to avoid last line
            
            if content_height < 1:
                stdscr.clear()
                try:
                    stdscr.addstr(0, 0, "Terminal too small")
                except curses.error:
                    pass
                stdscr.refresh()
                time.sleep(0.1)
                continue
            
            # Get current log lines
            with log_lock:
                current_logs = list(log_lines)  # Make a copy
                current_log_count = len(current_logs)
            
            # Initialize on first load
            if not initial_logs_loaded and current_log_count > 0:
                selected_index = current_log_count - 1  # Start at the last line
                last_log_count = current_log_count
                initial_logs_loaded = True
                auto_scroll = True
            
            # Check if new lines were added
            if current_log_count > last_log_count:
                # New lines were added
                if auto_scroll:
                    # If auto-scrolling, move selection to the new last line
                    selected_index = current_log_count - 1
                elif selected_index == last_log_count - 1:
                    # If we were at the last line, move selection to the new last line
                    selected_index = current_log_count - 1
                    auto_scroll = True  # Re-enable auto-scroll
                last_log_count = current_log_count
            
            if not current_logs:
                stdscr.clear()
                try:
                    stdscr.addstr(0, 0, "Waiting for log messages...", curses.color_pair(1))
                except curses.error:
                    pass
                stdscr.refresh()
                time.sleep(0.1)
                continue
            
            # Calculate how many lines the expanded line will take
            expanded_line_wrapped = []
            if expanded_index is not None and expanded_index < len(current_logs):
                expanded_line = current_logs[expanded_index]
                max_width = width - 3  # Leave space for ">" and margin
                
                # Word wrap the expanded line
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
            
            # Calculate display layout
            # We need to show: other log lines + expanded line (wrapped) + other log lines
            expanded_height = len(expanded_line_wrapped) if expanded_index is not None else 0
            
            # Adjust scroll to account for expanded line
            if expanded_index is not None:
                # Make sure expanded line is visible
                if expanded_index < scroll_offset:
                    scroll_offset = expanded_index
                elif expanded_index >= scroll_offset + content_height - expanded_height:
                    scroll_offset = expanded_index - (content_height - expanded_height) + 1
            
            # Selection mode - show list of log lines
            num_logs = len(current_logs)
            
            # Adjust selected_index if needed
            if selected_index >= num_logs:
                selected_index = max(0, num_logs - 1)
            if selected_index < 0:
                selected_index = 0
            
            # Calculate scroll offset to keep selected line visible
            # Account for expanded line height
            available_height = content_height - expanded_height if expanded_index is not None else content_height
            
            # If auto-scrolling, scroll to show the last line
            if auto_scroll:
                # Scroll to show the bottom (most recent lines)
                scroll_offset = max(0, num_logs - available_height)
            else:
                # Manual scrolling - keep selected line visible
                if selected_index < scroll_offset:
                    scroll_offset = selected_index
                elif selected_index >= scroll_offset + available_height:
                    scroll_offset = selected_index - available_height + 1
            
            stdscr.clear()
            
            # Header
            try:
                stdscr.addstr(0, 0, "=" * min(width, curses.COLS), curses.color_pair(1))
                scroll_indicator = " [AUTO-SCROLL]" if auto_scroll else ""
                header_text = f" Debug Log ({num_logs} lines){scroll_indicator} - Use UP/DOWN to navigate, ENTER to expand, Q to quit "
                stdscr.addstr(1, 0, header_text[:width-1], curses.color_pair(1))
            except curses.error:
                pass
            
            # Display log lines with in-place expansion
            y = header_height
            max_y = height - footer_height - 1  # Don't use last line
            
            # Calculate which log lines to show
            # We need to interleave regular lines with the expanded line
            display_start = max(0, scroll_offset)
            # Adjust display_end to account for expanded line taking multiple rows
            display_end = min(num_logs, scroll_offset + available_height)
            
            for i in range(display_start, display_end):
                log_index = i
                
                if y >= max_y:
                    break
                
                # Check if this is the expanded line
                if log_index == expanded_index:
                    # Show expanded line content (multiple wrapped lines)
                    for wrapped_line in expanded_line_wrapped:
                        if y >= max_y:
                            break
                        try:
                            stdscr.addstr(y, 0, ">", curses.color_pair(3))
                            stdscr.addstr(y, 2, wrapped_line[:width - 3], curses.color_pair(4))
                        except curses.error:
                            pass
                        y += 1
                    continue
                
                # Regular log line
                line = current_logs[log_index]
                
                # Preview first 100 characters
                preview = line[:100]
                if len(line) > 100:
                    preview += "..."
                
                # Truncate to fit screen
                display_line = preview[:width - 3]
                
                # Highlight selected line
                try:
                    if log_index == selected_index:
                        stdscr.addstr(y, 0, ">", curses.color_pair(3))
                        stdscr.addstr(y, 1, display_line, curses.color_pair(4))
                    else:
                        stdscr.addstr(y, 1, display_line)
                except curses.error:
                    pass
                
                y += 1
            
            # Footer (avoid last line)
            footer_y = height - 2
            if footer_y >= 0:
                try:
                    stdscr.addstr(footer_y, 0, "=" * min(width, curses.COLS))
                    if num_logs > 0:
                        footer_text = f" Line {selected_index + 1}/{num_logs} - {len(current_logs[selected_index])} chars "
                        stdscr.addstr(footer_y, 1, footer_text[:width-2], curses.color_pair(2))
                except curses.error:
                    pass
            
            stdscr.refresh()
            
            # Handle input
            stdscr.timeout(100)
            key = stdscr.getch()
            
            if key == curses.KEY_UP:
                if expanded_index is not None:
                    # In expanded mode, UP/DOWN closes expansion
                    expanded_index = None
                elif selected_index > 0:
                    selected_index -= 1
                    auto_scroll = False  # User is manually navigating
            elif key == curses.KEY_DOWN:
                if expanded_index is not None:
                    # In expanded mode, UP/DOWN closes expansion
                    expanded_index = None
                elif selected_index < num_logs - 1:
                    selected_index += 1
                    # If we're at the last line, enable auto-scroll
                    if selected_index == num_logs - 1:
                        auto_scroll = True
                    else:
                        auto_scroll = False  # User is manually navigating
            elif key == ord('\n') or key == ord('\r'):  # ENTER
                if expanded_index is not None:
                    # If already expanded, close it
                    expanded_index = None
                elif num_logs > 0 and selected_index < num_logs:
                    # Expand the selected line
                    expanded_index = selected_index
            elif key == ord('q') or key == 27:  # 'q' or ESC
                break
    
    except KeyboardInterrupt:
        pass
    finally:
        # Restore stdout
        sys.stdout = original_stdout
        running.clear()
        
        # Clean up curses
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()


if __name__ == "__main__":
    curses.wrapper(main)

