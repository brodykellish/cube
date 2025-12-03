"""
Clean menu navigation system with proper state management.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from .actions import MenuAction, NavigateAction, BackAction
from .menu_states import MenuState


@dataclass
class MenuContext:
    """Context passed to menu states for rendering and input handling."""
    width: int
    height: int
    settings: Dict[str, Any]


class MenuNavigator:
    """
    Manages menu navigation with a proper state stack.

    This replaces the string-based state transition system with
    a cleaner action-based approach.
    """

    def __init__(self, width: int, height: int, settings: Dict[str, Any]):
        """Initialize the menu navigator."""
        self.context = MenuContext(width, height, settings)
        self.state_stack: List[MenuState] = []
        self.current_state: Optional[MenuState] = None
        self.menu_registry: Dict[str, MenuState] = {}

    def register_menu(self, name: str, menu: MenuState) -> None:
        """Register a menu state."""
        self.menu_registry[name] = menu

    def push_state(self, state_name: str) -> None:
        """Push current state to stack and navigate to new state."""
        if self.current_state:
            self.state_stack.append(self.current_state)
        self.navigate_to(state_name)

    def pop_state(self) -> bool:
        """Pop state from stack and return to it. Returns False if stack is empty."""
        if self.state_stack:
            self.current_state = self.state_stack.pop()
            return True
        return False

    def navigate_to(self, state_name: str) -> None:
        """Navigate directly to a named state."""
        if state_name in self.menu_registry:
            self.current_state = self.menu_registry[state_name]
        else:
            raise ValueError(f"Unknown menu state: {state_name}")

    def handle_action(self, action: MenuAction) -> Optional[MenuAction]:
        """
        Handle a menu action.

        Returns:
            Action that needs to be handled by the controller (e.g., LaunchVisualizationAction)
            or None if the action was handled internally.
        """
        if isinstance(action, NavigateAction):
            self.navigate_to(action.target)
            return None
        elif isinstance(action, BackAction):
            if not self.pop_state():
                # If stack is empty, return to main menu
                self.navigate_to('main')
            return None
        else:
            # Action needs external handling (visualization launch, quit, etc.)
            return action

    def render(self, renderer) -> None:
        """Render the current menu state."""
        if self.current_state:
            self.current_state.render(renderer, self.context)

    def handle_input(self, key: str) -> Optional[MenuAction]:
        """
        Handle input for current menu state.

        Returns:
            Action that needs external handling or None.
        """
        if self.current_state:
            action = self.current_state.handle_input(key, self.context)
            if action:
                return self.handle_action(action)
        return None