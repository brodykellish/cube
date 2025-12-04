"""
Menu context for passing state to menu components.
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class MenuContext:
    """Context passed to menu states for rendering and input handling."""
    width: int
    height: int
    settings: Dict[str, Any]
