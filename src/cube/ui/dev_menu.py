# src/cube/ui/dev_menu.py

from pathlib import Path
from typing import Optional, Any

import numpy as np

from cube.ui.debug_renderer import DebugRenderer
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
        menu_window,  # MenuWindow instance - now owns its own InputManager
        shaders_root: Path,
    ) -> None:
        self.width = width
        self.height = height
        self.settings = settings
        self.menu_window = menu_window
        self.menu_input_manager = menu_window.input_manager  # Access window's input manager
        self.shaders_root = shaders_root

        # Create layers
        self.menu_layer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.debug_pane_height = 256  # Fixed height for debug pane
        self.debug_layer = np.zeros((self.debug_pane_height, self.width, 3), dtype=np.uint8)
        self.debug_pane_visible = False
        self.base_window_height = height  # Store original window height
        self.debug_renderer = DebugRenderer()

        # Core menu objects
        self.context = MenuContext(width, height, settings)
        self.navigator = MenuNavigator(width, height, settings)
        self.renderer = MenuRenderer(self.menu_layer)
        

        # Input forwarding state
        self.input_forwarding_enabled = False
        self._forwarding_keyboard_source = None
        self._forwarding_midi_source = None
        self._last_t_key_state = False

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
        
        # Handle input forwarding toggle (always check 't' key, even when forwarding is active)
        # Check for 't' key directly from keyboard state (check keys_held to detect press)
        if self.menu_window.backend.keyboard:
            kb_state = self.menu_window.backend.keyboard.poll()
            t_key_held = 't' in kb_state.keys_held
            # Detect transition from not held to held (key press)
            if t_key_held and not self._last_t_key_state:
                self._toggle_input_forwarding()
            self._last_t_key_state = t_key_held
        
        # Handle debug toggle in MENU context (only process if menu has focus)
        # Note: Input is only polled when menu is focused, so this is safe
        if Action.TOGGLE_DEBUG in pressed_actions:
            self._toggle_debug_window()
        

        # If input forwarding is enabled, don't process menu navigation
        # (input will be forwarded to visualization instead)
        if not self.input_forwarding_enabled:
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
        dt: float = 0.0,
    ) -> None:
        """
        Render the current menu, compose framebuffer, apply corrections, and display.
        
        Args:
            dt: Delta time for FPS calculation
        """
        # Clear menu_layer
        self.menu_layer[:, :, :] = 0
        # Let MenuNavigator render current state into MenuRenderer
        self.navigator.render(self.renderer)
        
        
        # Get final framebuffer (stitches menu + debug pane if visible)
        framebuffer = self._get_framebuffer()
        
        # Apply corrections
        framebuffer = self.menu_window.backend.apply_corrections(
            framebuffer,
            self.settings.get('brightness', 90.0),
            self.settings.get('gamma', 1.0)
        )
        
        # Display
        self.menu_window.show_framebuffer(framebuffer)
    
    def _get_framebuffer(self) -> np.ndarray:
        """
        Get the final framebuffer for display, stitching menu and debug layers together.
        
        Returns:
            Numpy array matching the current window size
        """
        menu_height, menu_width = self.menu_layer.shape[:2]
        
        # Get current window size from backend (may have changed due to resize)
        current_window_height = self.menu_window.backend.window_height
        current_window_width = self.menu_window.backend.window_width
        
        # Render debug pane if visible
        if self.debug_pane_visible:
            # Fill debug layer with light blue background (only 256px tall)
            self.debug_layer[:, :] = (173, 216, 230)  # Light blue
            
            # Create framebuffer matching window size exactly
            framebuffer = np.zeros((current_window_height, current_window_width, 3), dtype=np.uint8)
            
            # Place menu at top (only up to menu_height)
            actual_menu_height = min(menu_height, current_window_height)
            actual_menu_width = min(menu_width, current_window_width)
            framebuffer[:actual_menu_height, :actual_menu_width] = self.menu_layer[:actual_menu_height, :actual_menu_width]
            
            # Place debug pane below menu (only 256px tall, not full window height)
            debug_start = actual_menu_height
            debug_end = min(debug_start + self.debug_pane_height, current_window_height)
            actual_debug_height = debug_end - debug_start
            if actual_debug_height > 0:
                framebuffer[debug_start:debug_end, :current_window_width] = self.debug_layer[:actual_debug_height, :current_window_width]
            
            return framebuffer
        else:
            # No debug pane - create framebuffer matching window size
            # If window was resized, we need to match it
            if current_window_height != menu_height or current_window_width != menu_width:
                framebuffer = np.zeros((current_window_height, current_window_width, 3), dtype=np.uint8)
                # Place menu in top portion
                actual_menu_height = min(menu_height, current_window_height)
                actual_menu_width = min(menu_width, current_window_width)
                framebuffer[:actual_menu_height, :actual_menu_width] = self.menu_layer[:actual_menu_height, :actual_menu_width]
                return framebuffer
            else:
                # Window size matches menu layer, return as-is
                return self.menu_layer.copy()
        

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

    def _toggle_debug_window(self) -> None:
        """Toggle debug pane visibility and resize window accordingly."""
        self.debug_pane_visible = not self.debug_pane_visible
        
        # Calculate new window height based on base height
        if self.debug_pane_visible:
            new_height = self.base_window_height + self.debug_pane_height
        else:
            new_height = self.base_window_height
        
        # Resize pygame window programmatically (bypass aspect ratio enforcement)
        if hasattr(self.menu_window, 'backend') and hasattr(self.menu_window.backend, 'pygame'):
            backend = self.menu_window.backend
            pygame = backend.pygame
            
            # Set flag to skip aspect ratio enforcement for this resize
            backend._ignore_aspect_ratio = True
            
            # Update window dimensions immediately (before resize event is processed)
            backend.window_height = new_height
            
            # Resize window (this will trigger a VIDEORESIZE event, which will be handled by handle_events)
            backend.screen = pygame.display.set_mode(
                (backend.window_width, new_height),
                pygame.RESIZABLE
            )

            print(f'[DevMenuUI] Debug pane {"shown" if self.debug_pane_visible else "hidden"}, window resizing to {backend.window_width}×{new_height}')
