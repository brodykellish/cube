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
        controller=None,  # Optional controller reference for accessing visualization data
    ) -> None:
        self.width = width
        self.height = height
        self.settings = settings
        self.menu_window = menu_window
        self.menu_input_manager = menu_window.input_manager  # Access window's input manager
        self.shaders_root = shaders_root
        self.controller = controller  # Store controller reference for accessing visualization data

        # Create layers at render resolution (same as menu)
        self.menu_layer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.debug_pane_height = 256  # Fixed height for debug pane (window resolution)
        # Debug layer should be at render resolution, not window resolution
        # Get scale from backend to calculate render height
        scale = menu_window.backend.scale if hasattr(menu_window, 'backend') else 1
        debug_pane_render_height = self.debug_pane_height // scale
        self.debug_layer = np.zeros((debug_pane_render_height, self.width, 3), dtype=np.uint8)
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
        if Action.TOGGLE_INPUT_FORWARDING in pressed_actions:
            self._toggle_input_forwarding()
        
        # Handle debug toggle in MENU context (only process if menu has focus)
        # Note: Input is only polled when menu has focus, so this is safe
        if Action.TOGGLE_DEBUG in pressed_actions:
            self._toggle_debug_window()
        
        # Handle fullscreen toggle for visualization window (when debug pane is visible)
        if Action.TOGGLE_VISUALIZATION_FULLSCREEN in pressed_actions:
                self._toggle_visualization_fullscreen()
        
        # Handle mouse scroll for effects list when debug pane is visible
        if self.debug_pane_visible:
            if hasattr(self.menu_window, 'backend') and hasattr(self.menu_window.backend, 'mouse_scroll'):
                mouse_scroll = self.menu_window.backend.mouse_scroll
                if mouse_scroll != 0:
                    self.debug_renderer.handle_mouse_scroll(mouse_scroll)
        
        # Handle input forwarding toggle
        # (handled above via 't' key detection)
        

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
            Numpy array matching the internal render resolution (backend.width/height)
        """
        menu_height, menu_width = self.menu_layer.shape[:2]
        
        # Get scale and render resolution from backend
        scale = self.menu_window.backend.scale
        render_width = self.menu_window.backend.width
        
        # Render debug pane if visible
        if self.debug_pane_visible:
            # Fill debug layer with light blue background
            self.debug_layer[:, :] = (173, 216, 230)  # Light blue
            
            # Get visualization data if available
            renderer = None
            fps = 0.0
            preview_source = None
            if self.controller and self.controller.visualization_runner:
                try:
                    # Pass VisualizationRunner (not DAGRenderer) so get_debug_state() works
                    renderer = self.controller.visualization_runner
                    fps = self.controller.visualization_runner.get_fps() if hasattr(self.controller.visualization_runner, 'get_fps') else 0.0
                    preview_source = self.controller._latest_framebuffer
                except Exception:
                    pass
            
            # Render debug UI components in a horizontal row
            # Debug layer is at fixed render resolution
            
            # Ensure debug layer matches render width (may need to resize if window was resized)
            debug_layer_height, debug_layer_width = self.debug_layer.shape[:2]
            if debug_layer_width != render_width:
                # Resize debug layer to match current render width
                old_debug_layer = self.debug_layer
                self.debug_layer = np.zeros((debug_layer_height, render_width, 3), dtype=np.uint8)
                # Copy old content if possible
                copy_width = min(debug_layer_width, render_width)
                self.debug_layer[:, :copy_width] = old_debug_layer[:, :copy_width]
                # Fill rest with blue
                if render_width > copy_width:
                    self.debug_layer[:, copy_width:render_width] = (173, 216, 230)
                debug_layer_width = render_width
            
            # Calculate widths for each element (divide available width)
            num_elements = 3  # effects, preview, debug_info
            element_width = render_width // num_elements
            x_positions = [i * element_width for i in range(num_elements)]
            
            # Get beat phase/pulse from renderer if available
            beat_phase = 0.0
            beat_pulse = 0.0
            if renderer:
                try:
                    debug_state = renderer.get_debug_state()
                    beat_phase = float(debug_state.get('beat_phase', 0.0))
                    beat_pulse = float(debug_state.get('beat_pulse', 0.0))
                except Exception:
                    pass
            
            # Get input manager for effects list
            viz_input_manager = None
            if self.controller and self.controller.viz_window:
                viz_input_manager = self.controller.viz_window.input_manager
            
            # Element 1: Effects list (left) - using pygame font rendering
            effects_rendered = self.debug_renderer.render_effects_list_pygame(
                element_width, debug_layer_height, renderer, viz_input_manager
            )
            self.debug_layer[:, x_positions[0]:x_positions[0] + element_width] = effects_rendered[:, :element_width]
            
            # Element 3: Preview window
            preview_rendered = self.debug_renderer.render_preview(
                element_width, debug_layer_height, preview_source
            )
            self.debug_layer[:, x_positions[1]:x_positions[1] + element_width] = preview_rendered[:, :element_width]
            
            # Element 4: Debug info (FPS, parameters, resolutions) (right)
            viz_window = None
            if self.controller and self.controller.viz_window:
                viz_window = self.controller.viz_window
            debug_info_rendered = self.debug_renderer.render_debug_info(
                element_width, debug_layer_height, fps, renderer, viz_window
            )
            self.debug_layer[:, x_positions[2]:x_positions[2] + element_width] = debug_info_rendered[:, :element_width]
            
            # Total framebuffer height: menu at original resolution + debug pane
            total_render_height = menu_height + debug_layer_height
            
            # Create framebuffer: menu at original resolution + debug pane appended
            framebuffer = np.zeros((total_render_height, render_width, 3), dtype=np.uint8)
            
            # Place menu at top at its original resolution (no scaling/distortion)
            actual_menu_width = min(menu_width, render_width)
            framebuffer[:menu_height, :actual_menu_width] = self.menu_layer[:, :actual_menu_width]
            
            # Place debug pane below menu (already at render resolution, no scaling needed)
            debug_start = menu_height
            debug_end = total_render_height
            
            # Copy debug layer directly into framebuffer (both are at render resolution)
            copy_height = min(debug_layer_height, total_render_height - debug_start)
            copy_width = min(debug_layer_width, render_width)
            framebuffer[debug_start:debug_start + copy_height, :copy_width] = self.debug_layer[:copy_height, :copy_width]
            # Fill rest with blue if needed
            if render_width > copy_width:
                framebuffer[debug_start:debug_start + copy_height, copy_width:render_width] = (173, 216, 230)
            
            return framebuffer
        else:
            # No debug pane - return menu layer at its original resolution
            # Menu layer is already at render resolution, return as-is
            return self.menu_layer.copy()
        

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _toggle_input_forwarding(self) -> None:
        """Toggle input forwarding state and notify controller."""
        self.input_forwarding_enabled = not self.input_forwarding_enabled
        # Controller will handle the actual forwarding setup via _update_input_forwarding()
        if self.controller:
            self.controller._update_input_forwarding()
        print(f"[DevMenuUI] Input forwarding {'enabled' if self.input_forwarding_enabled else 'disabled'}")

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

    def _toggle_visualization_fullscreen(self) -> None:
        """Toggle fullscreen mode for visualization window."""
        if not self.controller or not self.controller.viz_window:
            return
        
        # Get current fullscreen state from backend
        viz_backend = self.controller.viz_window.backend
        is_fullscreen = getattr(viz_backend, '_is_fullscreen', False)
        
        # Toggle fullscreen
        self.controller.viz_window.set_fullscreen(not is_fullscreen)
        print(f"[DevMenu] Visualization window fullscreen: {not is_fullscreen}")
    
    def _toggle_debug_window(self) -> None:
        """Toggle debug pane visibility and resize window accordingly."""
        # Get current window height
        current_height = self.menu_window.backend.window_height

        print(f"Current window size: (WxH): {self.menu_window.backend.window_width}x{self.menu_window.backend.window_height}")
        print(f"Current menu size: (WxH): {self.menu_layer.shape[1]}x{self.menu_layer.shape[0]}")
        print(f"Current debug pane size: (WxH): {self.debug_layer.shape[1]}x{self.debug_layer.shape[0]}")
        
        # Toggle debug pane visibility
        self.debug_pane_visible = not self.debug_pane_visible
        
        # Calculate new window height: always add/subtract 256px
        if self.debug_pane_visible:
            # Add debug pane height to current window
            new_height = current_height + self.debug_pane_height
        else:
            # Remove debug pane height from current window
            new_height = max(self.debug_pane_height, current_height - self.debug_pane_height)  # Don't go below 256px

        print(f"New window size: (WxH): {self.menu_window.backend.window_width}x{new_height}")
        
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
