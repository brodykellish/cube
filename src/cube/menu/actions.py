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
    """Launch a visualization with specified configuration.
    
    pixel_mapper is optional - if None, the action may be used for editing
    rather than visualization (e.g., in prompt menu /list command).
    """
    shader_path: Optional[Path] = None
    video_path: Optional[Path] = None
    pixel_mapper: Optional[Literal['surface', 'cube']] = None


@dataclass
class MixerAction(MenuAction):
    """Mixer-related actions."""
    action_type: Literal['setup', 'select_shader', 'launch']
    channel: Optional[int] = None


@dataclass
class PromptAction(MenuAction):
    """Enter AI prompt interface for shader generation."""
    pass


@dataclass
class SaveDAGConfigAction(MenuAction):
    """Save current DAG configuration."""
    filename: str


@dataclass
class LoadDAGConfigAction(MenuAction):
    """Load a saved DAG configuration."""
    config_path: Path