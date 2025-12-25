"""
Application setup utilities for initialization.
"""
import sys
import threading
from pathlib import Path
from typing import List
from cube.utils.debug_log import StdoutCapture


def setup_debug_logging() -> tuple[List[str], threading.Lock, StdoutCapture, object]:
    """
    Set up debug logging with stdout capture.
    
    Returns:
        Tuple of (log_lines, log_lock, stdout_capture, original_stdout)
    """
    log_lines: List[str] = []
    log_lock = threading.Lock()
    stdout_capture = StdoutCapture(log_lines, log_lock)
    original_stdout = sys.stdout
    sys.stdout = stdout_capture
    
    return log_lines, log_lock, stdout_capture, original_stdout


def restore_stdout(original_stdout) -> None:
    """Restore original stdout."""
    import sys
    sys.stdout = original_stdout


def find_project_root() -> Path:
    """Find the project root directory by looking for marker files."""
    # Start from this file's directory
    current = Path(__file__).parent.parent.parent
    
    # Look for common project root markers
    markers = ['pyproject.toml', 'setup.py',
               'requirements.txt', 'effects_config.yml', '.git']
    
    # Walk up the directory tree
    for _ in range(10):  # Limit to 10 levels up
        # Check if any marker exists
        for marker in markers:
            if (current / marker).exists():
                return current
        # Move up one level
        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent
    
    # Fallback: use current working directory
    cwd = Path.cwd()
    print(
        f"[AppSetup] [WARNING] Could not find project root, using CWD: {cwd}")
    return cwd

