"""
Menu action definitions for cleaner state management.

Instead of returning strings that need parsing, menus return structured actions.
"""

from dataclasses import dataclass
from typing import Optional, Literal
from pathlib import Path


@dataclass
class MenuAction:
    """Base class for all menu actions."""
    pass


@dataclass
class NavigateAction(MenuAction):
    """Navigate to another menu state."""
    target: str  # Name of menu state to navigate to


@dataclass
class BackAction(MenuAction):
    """Go back to previous menu."""
    pass


@dataclass
class QuitAction(MenuAction):
    """Exit the application."""
    pass


@dataclass
class LaunchVisualizationAction(MenuAction):
    """Launch a visualization with specified configuration."""
    shader_path: Path
    pixel_mapper: Literal['surface', 'cube']
    primitive: Optional[str] = None  # For DRAW mode


@dataclass
class ShowRenderModeMenuAction(MenuAction):
    """Show render mode selection for a primitive."""
    primitive: str


@dataclass
class MixerAction(MenuAction):
    """Mixer-related actions."""
    action_type: Literal['setup', 'select_shader', 'launch']
    channel: Optional[int] = None