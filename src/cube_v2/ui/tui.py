"""
Curses-based terminal UI for cube_v2.

Provides a terminal interface for visualizing and controlling the DAG.
"""

import curses
import threading
import sys
from typing import Optional, List
from ..dag.dag import DAG
from ..core.mapping import MappingManager
from .views import DAGView, ParametersView, MappingsView
from .debug_log import DebugLogView, StdoutCapture


class TUI:
    """
    Terminal UI for cube_v2.
    
    Displays DAG structure, parameters, and mappings in 3 panes.
    Layout: DAG (left), Parameters + Mappings (right, stacked)
    """
    
    def __init__(self, dag: DAG, mapping_manager: MappingManager):
        """
        Initialize TUI.
        
        Args:
            dag: Shader DAG to display
            mapping_manager: Mapping manager to display
        """
        self.dag = dag
        self.mapping_manager = mapping_manager
        
        self.dag_view = DAGView(dag)
        self.params_view = ParametersView()
        self.mappings_view = MappingsView(mapping_manager)
        self.debug_log_view: Optional[DebugLogView] = None
        
        # Shared log storage for stdout capture (created in main thread)
        self.log_lines: List[str] = []
        self.log_lock = threading.Lock()
        self.stdout_capture: Optional[StdoutCapture] = None
        self.original_stdout = sys.stdout
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.stdscr: Optional[curses.window] = None
        self.panes: List[curses.window] = []
        self.last_height = 0
        self.last_width = 0
    
    def start(self):
        """Redirect stdout for capture (must be called before run())."""
        # Redirect stdout in the MAIN thread
        # This ensures all threads' print statements are captured
        self.stdout_capture = StdoutCapture(self.log_lines, self.log_lock)
        sys.stdout = self.stdout_capture
    
    def init_curses(self):
        """Initialize curses (non-blocking setup)."""
        if self.stdscr:
            return  # Already initialized
        
        try:
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
            curses.curs_set(0)
            
            # Clear screen immediately
            self.stdscr.clear()
            
            if curses.has_colors():
                curses.start_color()
                curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
                curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
                curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            
            # Initialize size tracking
            self.last_height, self.last_width = self.stdscr.getmaxyx()
            
            # Create initial panes
            self._create_panes()
            
            self.running = True
        except Exception as e:
            print(f"Failed to initialize curses: {e}", file=sys.stderr)
            self.running = False
    
    def update(self):
        """
        Update TUI (non-blocking, call from main loop).
        
        Returns True if should continue, False if should quit.
        """
        if not self.running:
            return False
        
        if not self.stdscr:
            self.init_curses()
            if not self.stdscr:
                return True  # Keep trying
        
        try:
            # Check for window resize
            try:
                current_height, current_width = self.stdscr.getmaxyx()
                if current_height != self.last_height or current_width != self.last_width:
                    self.last_height = current_height
                    self.last_width = current_width
                    self._create_panes()
            except curses.error:
                pass
            
            # Render
            try:
                self._render()
                self.stdscr.refresh()
            except curses.error:
                pass
            
            # Non-blocking getch
            self.stdscr.nodelay(True)
            try:
                key = self.stdscr.getch()
                if key == ord('q') or key == 27:  # 'q' or ESC
                    self.running = False
                    return False
                elif key == curses.KEY_RESIZE:
                    current_height, current_width = self.stdscr.getmaxyx()
                    self.last_height = current_height
                    self.last_width = current_width
                    self._create_panes()
                elif self.debug_log_view and key != -1:
                    # Forward input to debug log view (for navigation)
                    if key in (curses.KEY_UP, curses.KEY_DOWN, ord('\n'), ord('\r')):
                        self.debug_log_view.handle_input(key)
            except curses.error:
                pass
        except Exception as e:
            print(f"TUI update error: {e}", file=sys.stderr)
        
        return True
    
    def run(self):
        """
        Run TUI main loop in the current thread (blocking).
        
        This should be called from the main thread.
        """
        if self.running:
            return
        
        self.running = True
        
        try:
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
            curses.curs_set(0)
            
            # Clear screen immediately
            self.stdscr.clear()
            
            if curses.has_colors():
                curses.start_color()
                curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
                curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
                curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            
            # Initialize size tracking
            self.last_height, self.last_width = self.stdscr.getmaxyx()
            
            # Create initial panes
            self._create_panes()
            
            # Initial render
            self._render()
            self.stdscr.refresh()
            
            while self.running:
                # Check for window resize
                try:
                    current_height, current_width = self.stdscr.getmaxyx()
                    if current_height != self.last_height or current_width != self.last_width:
                        # Window was resized - recreate panes
                        self.last_height = current_height
                        self.last_width = current_width
                        self._create_panes()
                except curses.error:
                    pass
                
                # Render
                try:
                    self._render()
                    self.stdscr.refresh()
                except curses.error:
                    pass
                
                # Non-blocking getch with timeout
                self.stdscr.timeout(100)
                try:
                    key = self.stdscr.getch()
                    if key == ord('q') or key == 27:  # 'q' or ESC
                        self.running = False
                        break
                    elif key == curses.KEY_RESIZE:
                        # Handle explicit resize event
                        current_height, current_width = self.stdscr.getmaxyx()
                        self.last_height = current_height
                        self.last_width = current_width
                        self._create_panes()
                    elif self.debug_log_view:
                        # Forward input to debug log view (for navigation)
                        # Only handle if it's a debug log navigation key
                        if key in (curses.KEY_UP, curses.KEY_DOWN, ord('\n'), ord('\r')):
                            self.debug_log_view.handle_input(key)
                except curses.error:
                    pass
        except Exception as e:
            # Log error to stderr (original terminal)
            print(f"TUI error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        finally:
            if self.stdscr:
                try:
                    curses.nocbreak()
                    self.stdscr.keypad(False)
                    curses.echo()
                    curses.endwin()
                except:
                    pass
    
    def stop(self):
        """Stop TUI."""
        self.running = False
        
        # Restore stdout
        if self.stdout_capture:
            sys.stdout = self.original_stdout
    
    def _create_panes(self):
        """Create 4 panes: DAG (top-left), Parameters (top-right), Mappings (bottom-right), Debug Log (bottom-left)."""
        if not self.stdscr:
            return
        
        try:
            height, width = self.stdscr.getmaxyx()
        except curses.error:
            return
        
        # Ensure minimum size
        if height < 10 or width < 40:
            return
        
        # Clear existing panes
        self.panes.clear()
        
        # Calculate pane dimensions (4 quadrants)
        pane_height = height // 2
        pane_width = width // 2
        
        # Top-left: DAG
        try:
            pane1 = self.stdscr.subwin(pane_height, pane_width, 0, 0)
            if pane1:
                pane1.border()
                self.panes.append(pane1)
        except curses.error:
            pass
        
        # Top-right: Parameters
        try:
            pane2 = self.stdscr.subwin(pane_height, pane_width, 0, pane_width)
            if pane2:
                pane2.border()
                self.panes.append(pane2)
        except curses.error:
            pass
        
        # Bottom-left: Debug Log
        try:
            pane3 = self.stdscr.subwin(pane_height, pane_width, pane_height, 0)
            if pane3:
                pane3.border()
                self.panes.append(pane3)
                # Initialize or update debug log view
                if self.debug_log_view is None:
                    # Pass shared log storage and stdout capture
                    self.debug_log_view = DebugLogView(
                        pane3, 
                        log_lines=self.log_lines,
                        log_lock=self.log_lock,
                        stdout_capture=self.stdout_capture
                    )
                else:
                    # Update the window reference if panes were recreated
                    self.debug_log_view.window = pane3
        except curses.error:
            pass
        
        # Bottom-right: Mappings
        try:
            pane4 = self.stdscr.subwin(pane_height, pane_width, pane_height, pane_width)
            if pane4:
                pane4.border()
                self.panes.append(pane4)
        except curses.error:
            pass
    
    def _render(self):
        """Render all views in their panes."""
        if not self.stdscr or len(self.panes) < 4:
            return
        
        height, width = self.stdscr.getmaxyx()
        
        # Calculate pane dimensions (4 quadrants)
        pane_height = height // 2
        pane_width = width // 2
        
        # Content areas (inside borders)
        content_height = pane_height - 2
        content_width = pane_width - 2
        
        # Ensure content areas are valid
        if content_height < 1 or content_width < 1:
            return
        
        # Pane 1: DAG (top-left)
        dag_pane = self.panes[0]
        dag_pane.clear()
        dag_pane.border()
        dag_pane.addstr(0, 2, " DAG Structure ", curses.color_pair(1))
        dag_lines = self.dag_view.render(content_width, content_height)
        for i, line in enumerate(dag_lines[:content_height]):
            try:
                dag_pane.addstr(i + 1, 1, line[:content_width])
            except curses.error:
                pass
        
        # Pane 2: Parameters (top-right)
        params_pane = self.panes[1]
        params_pane.clear()
        params_pane.border()
        params_pane.addstr(0, 2, " Parameters ", curses.color_pair(2))
        params_lines = self.params_view.render(content_width, content_height)
        for i, line in enumerate(params_lines[:content_height]):
            try:
                params_pane.addstr(i + 1, 1, line[:content_width])
            except curses.error:
                pass
        
        # Pane 3: Debug Log (bottom-left)
        debug_pane = self.panes[2]
        debug_pane.clear()
        debug_pane.border()
        debug_pane.addstr(0, 2, " Debug Log ", curses.color_pair(4) if curses.has_colors() else 0)
        if self.debug_log_view:
            self.debug_log_view.render()
        
        # Pane 4: Mappings (bottom-right)
        mappings_pane = self.panes[3]
        mappings_pane.clear()
        mappings_pane.border()
        mappings_pane.addstr(0, 2, " Mappings ", curses.color_pair(3))
        mappings_lines = self.mappings_view.render(content_width, content_height)
        for i, line in enumerate(mappings_lines[:content_height]):
            try:
                mappings_pane.addstr(i + 1, 1, line[:content_width])
            except curses.error:
                pass
