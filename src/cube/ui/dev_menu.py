# src/cube/ui/dev_menu.py

from pathlib import Path
from typing import Optional, Any

import numpy as np

from cube.menu.navigation import MenuNavigator
from cube.menu.menu_states import (
    MainMenu,
    VisualizationModeSelect,
    ShaderBrowser,
    SettingsMenu,
)
from cube.menu.prompt_menu import PromptMenuState
from cube.menu.menu_renderer import MenuRenderer
from cube.menu.actions import (
    MenuAction,
    LaunchVisualizationAction,
    QuitAction,
    PromptAction,
    MixerAction,
)
from cube.menu.menu_context import MenuContext
from cube.input.actions import Action, InputContext
from cube.input.input_manager import InputManager
from cube.ui.debug_renderer import DebugRenderer


class DevMenuUI:
    """
    Desktop PyGame menu UI wrapper.

    Owns:
      - MenuNavigator + menu states
      - MenuRenderer
      - Drawing into a numpy framebuffer (menu_layer)
    """

    def __init__(
        self,
        width: int,
        height: int,
        settings: dict,
        menu_layer: np.ndarray,
        menu_window,  # MenuWindow instance - now owns its own InputManager
        shaders_root: Path,
    ) -> None:
        self.width = width
        self.height = height
        self.settings = settings
        self.menu_layer = menu_layer
        self.menu_window = menu_window
        self.menu_input_manager = menu_window.input_manager  # Access window's input manager
        self.shaders_root = shaders_root

        # Core menu objects
        self.context = MenuContext(width, height, settings)
        self.navigator = MenuNavigator(width, height, settings)
        self.renderer = MenuRenderer(self.menu_layer)
        
        # Debug renderer for menu window
        self.debug_renderer = DebugRenderer()
        self.fps_current = 0.0
        self.fps_counter = 0
        import time
        self.fps_last_time = time.time()

        self._register_menus()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def update(self, dt: float) -> Optional[MenuAction]:
        """
        Update menu state and process input.

        Returns:
            MenuAction (e.g. LaunchVisualizationAction, QuitAction) or None.
        """
        # Poll input (already done in controller; here we just read state)
        pressed_actions = self.menu_input_manager.get_pressed_actions()
        
        # Handle debug toggle in MENU context (only process if menu has focus)
        # Note: Input is only polled when menu is focused, so this is safe
        if Action.TOGGLE_DEBUG in pressed_actions:
            self._toggle_debug()
        
        # Handle preview toggle in MENU context
        if Action.TOGGLE_PREVIEW in pressed_actions:
            print("HERE")
            self._toggle_preview()

        # Map high-level actions → legacy key strings for MenuNavigator
        key_for_action: Optional[str] = None
        if self.menu_input_manager.is_action_pressed(Action.NAVIGATE_UP):
            key_for_action = "up"
        elif self.menu_input_manager.is_action_pressed(Action.NAVIGATE_DOWN):
            key_for_action = "down"
        elif self.menu_input_manager.is_action_pressed(Action.NAVIGATE_LEFT):
            key_for_action = "left"
        elif self.menu_input_manager.is_action_pressed(Action.NAVIGATE_RIGHT):
            key_for_action = "right"
        elif self.menu_input_manager.is_action_pressed(Action.CONFIRM):
            key_for_action = "enter"
        elif (
            self.menu_input_manager.is_action_pressed(Action.BACK)
            or self.menu_input_manager.is_action_pressed(Action.CANCEL)
        ):
            key_for_action = "escape"

        if key_for_action:
            action = self.navigator.handle_input(key_for_action)
            if action:
                return action

        # Paste handling (for prompt menu)
        paste_text = self.menu_input_manager.get_paste_text()
        if paste_text and hasattr(self.navigator.current_state, "handle_paste"):
            self.navigator.current_state.handle_paste(paste_text)

        # Per-state update hook
        action = self.navigator.update(dt)
        if isinstance(action, MenuAction):
            # Handle actions that don't require cross-thread coordination
            if isinstance(action, PromptAction):
                self.navigator.navigate_to('prompt')
                return None
            if isinstance(action, MixerAction):
                print(f"Mixer action not yet implemented: {action}")
                return None
            # Actions requiring cross-thread coordination (LaunchVisualizationAction, QuitAction)
            # are returned to controller
            return action

        return None

    def render(
        self, 
        debug_layer: Optional[np.ndarray] = None, 
        renderer: Optional[Any] = None, 
        dt: float = 0.0,
    ) -> None:
        """
        Render the current menu into `menu_layer` and optionally render debug overlay.
        
        Args:
            debug_layer: Debug layer to render into (can be same as menu_layer or separate)
            renderer: Optional renderer instance for debug info (from visualization)
            dt: Delta time for FPS calculation
        """
        # Clear menu_layer
        self.menu_layer[:, :, :] = 0
        # Let MenuNavigator render current state into MenuRenderer
        self.navigator.render(self.renderer)
        
        # Update FPS
        if dt > 0:
            self.fps_counter += 1
            import time
            current_time = time.time()
            if current_time - self.fps_last_time >= 1.0:
                self.fps_current = self.fps_counter / (current_time - self.fps_last_time)
                self.fps_counter = 0
                self.fps_last_time = current_time
        
        # Render debug overlay if enabled and debug_layer provided
        if debug_layer is not None:
            self.debug_renderer.render(
                debug_layer=debug_layer,
                settings=self.settings,
                fps=self.fps_current,
                renderer=renderer,
                input_manager=self.menu_input_manager,
                context='menu',
            )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _register_menus(self) -> None:
        """Register all menu states with the navigator."""
        self.navigator.register_menu("main", MainMenu())
        self.navigator.register_menu("visualize", VisualizationModeSelect())
        self.navigator.register_menu("surface_browser", ShaderBrowser("surface"))
        self.navigator.register_menu("cube_browser", ShaderBrowser("cube"))
        self.navigator.register_menu("settings", SettingsMenu())

        # Prompt menu gets the shaders root for AI editing
        self.navigator.register_menu(
            "prompt",
            PromptMenuState(self.width, self.height, self.shaders_root),
        )

        self.navigator.navigate_to("main")

    def _toggle_debug(self) -> None:
        """Toggle menu_debug_ui flag in settings (only when menu is focused)."""
        self.settings["menu_debug_ui"] = not self.settings.get("menu_debug_ui", False)
        status = "enabled" if self.settings["menu_debug_ui"] else "disabled"
        print(f"[DevMenuUI] Menu Debug UI {status}")
    
    def _toggle_preview(self) -> None:
        """Toggle preview_mode flag in settings (only when menu is focused)."""
        self.settings["preview_mode"] = not self.settings.get("preview_mode", False)
        status = "enabled" if self.settings["preview_mode"] else "disabled"
        print(f"[DevMenuUI] Preview mode {status} (press 'p' to toggle)")