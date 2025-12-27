# src/cube/ui/dev_menu.py

from pathlib import Path
from typing import Optional

import numpy as np

from cube.ui.debug_ui import DebugUIRenderer, DebugUIData, collect_debug_data
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
    PromptAction,
    MixerAction,
    SaveDAGConfigAction,
    BackAction,
)
from cube.menu.menu_context import MenuContext
from cube.input.actions import Action


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
        self.debug_renderer = DebugUIRenderer()
        self.debug_data = DebugUIData()  # Persistent data object (for scroll state)

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
                    self.debug_data.effects_scroll_offset = max(0, self.debug_data.effects_scroll_offset - mouse_scroll)

        # If input forwarding is enabled, don't process menu navigation
        # (input will be forwarded to visualization instead)
        if not self.input_forwarding_enabled:
            # Check if current state is a text input state (needs raw character input)
            is_text_input = hasattr(self.navigator.current_state, 'input_buffer')
            
            # Map high-level actions → legacy key strings for MenuNavigator
            key_for_action: Optional[str] = None
            
            # For text input states, check for raw character keys first
            if is_text_input and hasattr(self.menu_window, 'backend'):
                # Get raw key from backend's last event processing
                # The backend processes events in handle_events(), which is called by process_events()
                # We need to check the keyboard state directly
                if hasattr(self.menu_window.backend, 'keyboard'):
                    # Get the last keyboard state (events are already processed)
                    # We'll check for character keys that might not be mapped to actions
                    # Note: This is a bit of a hack, but necessary for text input
                    try:
                        # The keyboard.poll() was already called by backend.handle_events()
                        # We need to access the last key press differently
                        # For now, we'll rely on action mapping for special keys and
                        # check if there are unmapped character keys
                        pass  # Will handle character input through action mapping below
                    except:
                        pass
            
            # Map actions to keys (this handles both special keys and some character keys)
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
            
            # For text input, we also need to pass through character keys
            # The prompt menu works because it receives keys directly
            # Let's check the backend's last event result for raw keys
            if is_text_input and not key_for_action:
                # Try to get raw key from backend events
                # The backend's handle_events returns {'key': ...} with raw character keys
                # But this is already processed. We need a different approach.
                # For now, character input will work through the existing key system
                # if the keyboard source properly exposes character keys
                pass

            if key_for_action:
                action = self.navigator.handle_input(key_for_action)
                if action:
                    return action

            # Paste handling (for prompt menu and text input)
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
                if isinstance(action, SaveDAGConfigAction) and not action.filename:
                    # Show text input prompt for filename
                    from cube.menu.text_input_prompt import TextInputPrompt
                    from cube.menu.actions import SaveDAGConfigAction as SaveAction
                    
                    def on_confirm(filename: str):
                        if filename.strip():
                            return SaveAction(filename=filename.strip())
                        return BackAction()
                    
                    def on_cancel():
                        return BackAction()
                    
                    prompt = TextInputPrompt(
                        prompt_text="ENTER FILENAME",
                        on_confirm=on_confirm,
                        on_cancel=on_cancel
                    )
                    self.navigator.register_menu("save_config_prompt", prompt)
                    self.navigator.push_state("save_config_prompt")
                    return None
                # Actions requiring cross-thread coordination (LaunchVisualizationAction, QuitAction)
                # are returned to controller
                return action

        return None

    def render(self) -> None:
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
        render_width = self.menu_window.backend.width
        
        # Render debug pane if visible
        if self.debug_pane_visible:
            # Fill debug layer with light blue background
            self.debug_layer[:, :] = (173, 216, 230)  # Light blue
            
            # Collect all debug data (with error handling to prevent UI from disappearing)
            try:
                visualization_runner = getattr(self.controller, 'visualization_runner', None)
                viz_window = getattr(self.controller, 'viz_window', None)
                viz_input_manager = getattr(viz_window, 'input_manager', None) if viz_window else None
                preview_framebuffer = None
                
                # Only use preview framebuffer if visualization is actually running
                if hasattr(self.controller, '_latest_framebuffer') and self.controller._latest_framebuffer is not None:
                    # Check if visualization is still running before using the framebuffer
                    viz_running = False
                    if visualization_runner:
                        try:
                            if hasattr(visualization_runner, '_thread') and visualization_runner._thread:
                                viz_running = visualization_runner._thread.is_alive()
                            if viz_window and hasattr(viz_window, 'is_focused'):
                                viz_running = viz_running and viz_window.is_focused()
                        except Exception:
                            pass
                    
                    if viz_running:
                        preview_framebuffer = self.controller._latest_framebuffer
                    # If not running, preview_framebuffer stays None (will show placeholder)
                
                # Collect debug data (preserve scroll offset from persistent data)
                scroll_offset = self.debug_data.effects_scroll_offset
                debug_data = collect_debug_data(
                    visualization_runner=visualization_runner,
                    viz_window=viz_window,
                    preview_framebuffer=preview_framebuffer,
                    viz_input_manager=viz_input_manager,
                )
                debug_data.effects_scroll_offset = scroll_offset
                self.debug_data = debug_data  # Update persistent data
            except Exception as e:
                # If data collection fails, use empty data but keep UI visible
                print(f"[DevMenuUI] Error collecting debug data: {e}")
                import traceback
                traceback.print_exc()
                # Keep using previous debug_data to maintain UI visibility
                debug_data = self.debug_data

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
            
            # Element 1: Effects list (left) - using pygame font rendering
            effects_rendered = self.debug_renderer.render_effects_list_pygame(
                element_width, debug_layer_height, debug_data
            )
            self.debug_layer[:, x_positions[0]:x_positions[0] + element_width] = effects_rendered[:, :element_width]
            
            # Element 2: Preview window
            preview_rendered = self.debug_renderer.render_preview(
                element_width, debug_layer_height, debug_data
            )
            self.debug_layer[:, x_positions[1]:x_positions[1] + element_width] = preview_rendered[:, :element_width]
            
            # Element 3: Debug info (FPS, parameters, resolutions) (right)
            debug_info_rendered = self.debug_renderer.render_debug_info(
                element_width, debug_layer_height, debug_data
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
        from pathlib import Path
        from cube.menu.dag_config_browser import DAGConfigBrowser
        from cube.utils.app_setup import find_project_root
        
        project_root = find_project_root()
        configs_dir = project_root / 'dag_configs'
        
        self.navigator.register_menu("main", MainMenu())
        self.navigator.register_menu("visualize", VisualizationModeSelect())
        self.navigator.register_menu("surface_browser", ShaderBrowser("surface"))
        self.navigator.register_menu("cube_browser", ShaderBrowser("cube"))
        self.navigator.register_menu("settings", SettingsMenu())
        self.navigator.register_menu("dag_config_browser", DAGConfigBrowser(configs_dir))

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
