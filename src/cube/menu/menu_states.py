"""
Refactored menu states using clean action-based system.
"""

from pathlib import Path
from typing import Optional, List, Tuple
from abc import ABC, abstractmethod
from .actions import (
    MenuAction, NavigateAction, BackAction, QuitAction,
    LaunchVisualizationAction, PromptAction, ShaderSelectionAction
)
from .menu_context import MenuContext
from .menu_renderer import MenuRenderer
from .menu_utils import ScrollableList, MenuHeader, SliderConfig


class MenuState(ABC):
    """Base class for all menu states."""

    def __init__(self, name: str):
        self.name = name
        if self.name is None:
            self.name = self.__class__.__name__

    @abstractmethod
    def render(self, renderer, context: MenuContext) -> None:
        """Render the menu."""
        pass

    @abstractmethod
    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        """Handle input and return an action if needed."""
        pass


class MainMenu(MenuState):
    """Main menu - entry point for all functionality."""

    def __init__(self):
        super().__init__('main')
        
        self.options = [
            ("VISUALIZE", "visualize"),
            ("PROMPT", "prompt"),
            ("MIXER", "mixer_setup"),
            ("SETTINGS", "settings"),
            ("EXIT", None),
        ]
        self.list = ScrollableList(self.options)

    def render(self, renderer: MenuRenderer, context: MenuContext):
        """Render main menu."""
        renderer.clear((0, 0, 0))

        # Header
        header_height = MenuHeader.render(renderer, "CUBE CONTROL")

        # Calculate available space
        available_height = context.height - header_height

        # Render list
        self.list.render(
            renderer, context,
            y_start=header_height,
            available_height=available_height,
            format_item=lambda item: item[0]
        )

    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        if key == 'up':
            self.list.move_up()
        elif key == 'down':
            self.list.move_down()
        elif key == 'enter':
            selected = self.list.get_selected()
            if selected:
                label, target = selected
                if label == "EXIT":
                    return QuitAction()
                elif label == "PROMPT":
                    return PromptAction()
                elif target:
                    return NavigateAction(target=target)
        elif key in ('back', 'escape'):
            return QuitAction()
        return None


class VisualizationModeSelect(MenuState):
    """Select between Surface and Cube rendering modes."""

    def __init__(self):
        super().__init__('visualize')
        
        self.options = [
            ("SURFACE", "surface_browser"),
            ("CUBE", "cube_browser"),
            ("BACK", None),
        ]
        self.list = ScrollableList(self.options)

    def render(self, renderer, context: MenuContext):
        renderer.clear((0, 0, 0))

        # Header
        header_height = MenuHeader.render(renderer, "VISUALIZATION MODE")

        # Calculate available space
        available_height = context.height - header_height

        # Render list
        self.list.render(
            renderer, context,
            y_start=header_height,
            available_height=available_height,
            format_item=lambda item: item[0]
        )

    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        if key == 'up':
            self.list.move_up()
        elif key == 'down':
            self.list.move_down()
        elif key == 'enter':
            selected = self.list.get_selected()
            if selected:
                label, target = selected
                if label == "BACK":
                    return BackAction()
                elif target:
                    return NavigateAction(target=target)
        elif key in ('back', 'escape'):
            return BackAction()
        return None


class ShaderBrowser(MenuState):
    """Browse and select shaders for visualization with optional pixel mapper selection."""

    def __init__(self, pixel_mapper: Optional[str] = None, include_pixel_mapper: bool = True):
        """
        Initialize shader browser.

        Args:
            pixel_mapper: Fixed pixel mapper ('surface' or 'cube'), or None to let user choose
            include_pixel_mapper: If True, include pixel mapper selection as first stage
        """
        super().__init__('shader_browser')

        self.include_pixel_mapper = include_pixel_mapper
        self.pixel_mapper = pixel_mapper  # Can be None if user will select
        self.selected_pixel_mapper: Optional[str] = pixel_mapper  # User's selection

        # Three-stage browsing (if pixel mapper included): pixel_mapper -> directory -> shader
        # Two-stage browsing (if pixel mapper fixed): directory -> shader
        self.browsing_mode = "pixel_mapper" if (include_pixel_mapper and not pixel_mapper) else "directory"
        self.selected_directory: Optional[str] = None

        # Pixel mapper options (if needed)
        self.pixel_mappers = [
            ("pixel_mapper", "SURFACE", "surface"),
            ("pixel_mapper", "CUBE", "cube"),
            ("action", "BACK", None)
        ]

        # Available shader directories
        self.directories = [
            ("directory", "PRIMITIVES", "primitives"),
            ("directory", "GRAPHICS", "graphics"),
            ("directory", "GENERATED", "generated"),
            ("action", "BACK", None)
        ]

        # Current items list
        self.items = []
        self.list = ScrollableList(self.items)

        # Start with appropriate screen
        if self.browsing_mode == "pixel_mapper":
            self._show_pixel_mapper_selection()
        else:
            self._show_directory_selection()

    def _show_pixel_mapper_selection(self):
        """Show the pixel mapper selection menu."""
        self.browsing_mode = "pixel_mapper"
        self.selected_pixel_mapper = None
        self.items = self.pixel_mappers.copy()
        self.list.set_items(self.items)

    def _show_directory_selection(self):
        """Show the directory selection menu."""
        self.browsing_mode = "directory"
        self.selected_directory = None
        self.items = self.directories.copy()
        self.list.set_items(self.items)

    def _load_glsl_directory(self, directory: Path) -> List[tuple]:
        """Load all glsl files in a directory into a list of tuples (type, name, path)."""
        shaders = []
        if directory.exists():
            for shader_path in sorted(directory.glob("*.glsl")):
                # Store full path
                shaders.append(("shader", shader_path.stem, shader_path))
        return shaders

    def _show_shader_selection(self, directory_name: str):
        """Show shaders from the selected directory."""
        self.browsing_mode = "shader"
        self.selected_directory = directory_name
        self.items = []

        # Load shaders from selected directory
        directory_path = Path("shaders") / directory_name
        shaders = self._load_glsl_directory(directory_path)

        if shaders:
            self.items.extend(shaders)
        else:
            self.items.append(("info", "NO SHADERS FOUND", None))

        # Add back option
        self.items.append(("action", "BACK", None))

        self.list.set_items(self.items)

    def render(self, renderer: MenuRenderer, context: MenuContext):
        renderer.clear((0, 0, 0))

        # Header changes based on browsing mode
        if self.browsing_mode == "pixel_mapper":
            title = "SELECT MODE"
            subtitle = "Choose rendering mode"
        elif self.browsing_mode == "directory":
            title = "SELECT DIRECTORY"
            # Show pixel mapper if selected, or if fixed
            pm = self.selected_pixel_mapper or self.pixel_mapper
            subtitle = f"[{pm.upper()}]" if pm else ""
        else:  # shader mode
            title = "SELECT SHADER"
            pm = self.selected_pixel_mapper or self.pixel_mapper
            subtitle = f"[{pm.upper()}] {self.selected_directory.upper()}" if pm else self.selected_directory.upper()

        header_height = MenuHeader.render(renderer, title, subtitle)

        if not self.items:
            renderer.draw_text("NO ITEMS FOUND", 0, y=header_height, color=(255, 100, 100), scale=1)
            return

        # Calculate available space
        available_height = context.height - header_height

        # Custom render function
        def format_item(item):
            item_type, name, _ = item
            if item_type == "pixel_mapper":
                return f"  {name}"
            elif item_type == "directory":
                return f"  {name}"
            elif item_type == "shader":
                return f"  {name}"
            elif item_type == "info":
                return f"  {name}"
            elif item_type == "action":
                return f"< {name}"
            return name

        # Render with custom formatting
        self.list.render(
            renderer, context,
            y_start=header_height,
            available_height=available_height,
            format_item=format_item,
            selected_color=(255, 255, 100),
            normal_color=(200, 200, 200)
        )

    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        if key == 'up':
            self.list.move_up()
        elif key == 'down':
            self.list.move_down()
        elif key == 'enter':
            selected = self.list.get_selected()
            if selected:
                item_type, name, data = selected

                if self.browsing_mode == "pixel_mapper":
                    # Pixel mapper selection mode
                    if item_type == "pixel_mapper":
                        # Store selection and move to directory selection
                        self.selected_pixel_mapper = data
                        self._show_directory_selection()
                    elif item_type == "action" and name == "BACK":
                        return BackAction()

                elif self.browsing_mode == "directory":
                    # Directory selection mode
                    if item_type == "directory":
                        # Navigate into directory
                        self._show_shader_selection(data)
                    elif item_type == "action" and name == "BACK":
                        # If we came from pixel mapper selection, go back to it
                        if self.include_pixel_mapper and not self.pixel_mapper:
                            self._show_pixel_mapper_selection()
                        else:
                            return BackAction()

                elif self.browsing_mode == "shader":
                    # Shader selection mode
                    if item_type == "shader":
                        # Return shader selection (not launch directly)
                        return ShaderSelectionAction(
                            shader_path=data,
                            pixel_mapper=self.selected_pixel_mapper or self.pixel_mapper
                        )
                    elif item_type == "action" and name == "BACK":
                        # Go back to directory selection
                        self._show_directory_selection()

        elif key in ('back', 'escape'):
            if self.browsing_mode == "shader":
                # Back goes to directory selection
                self._show_directory_selection()
            elif self.browsing_mode == "directory":
                # Back to pixel mapper selection or previous menu
                if self.include_pixel_mapper and not self.pixel_mapper:
                    self._show_pixel_mapper_selection()
                else:
                    return BackAction()
            elif self.browsing_mode == "pixel_mapper":
                # Back goes to previous menu
                return BackAction()

        return None


class SettingsMenu(MenuState):
    """Settings menu for system configuration."""

    def __init__(self):
        super().__init__('settings')
        
        self.options = [
            ("DEBUG UI", "debug_ui", "toggle"),
            ("DEBUG AXES", "debug_axes", "toggle"),
            ("BRIGHTNESS", "brightness", "slider"),
            ("GAMMA", "gamma", "slider"),
            ("FPS LIMIT", "fps_limit", "slider"),
            ("BACK TO MAIN", None, None),
        ]
        self.list = ScrollableList(self.options)

        # Define slider configurations
        self.slider_configs = {
            "brightness": SliderConfig(min_value=10.0, max_value=90.0, increment=5.0, format_string="{:.0f}%"),
            "gamma": SliderConfig(min_value=0.5, max_value=3.0, increment=0.1, format_string="{:.1f}"),
            "fps_limit": SliderConfig(min_value=10.0, max_value=60.0, increment=5.0, format_string="{:.0f}"),
        }

    def render(self, renderer, context: MenuContext):
        renderer.clear((0, 0, 0))

        # Header
        header_height = MenuHeader.render(renderer, "SETTINGS")

        # Custom rendering for settings with values
        available_height = context.height - header_height
        item_height = 7
        visible_items = available_height // item_height

        # Update scroll
        selected_idx = self.list.get_selected_index()
        if selected_idx < self.list.scroll_offset:
            self.list.scroll_offset = selected_idx
        elif selected_idx >= self.list.scroll_offset + visible_items:
            self.list.scroll_offset = selected_idx - visible_items + 1

        # Render items manually to show values
        y_start = header_height
        for i in range(self.list.scroll_offset, min(len(self.options), self.list.scroll_offset + visible_items)):
            label, setting_key, setting_type = self.options[i]
            y = y_start + (i - self.list.scroll_offset) * item_height

            color = (255, 255, 100) if i == selected_idx else (200, 200, 200)
            renderer.draw_text(label, 15, y, color=color, scale=1)

            if i == selected_idx:
                renderer.draw_text(">", 5, y, color=(255, 255, 100), scale=1)

            # Show current value
            if setting_key and setting_type == "toggle":
                value = "ON" if context.settings.get(setting_key, False) else "OFF"
                value_color = (100, 255, 100) if value == "ON" else (255, 100, 100)
                renderer.draw_text(value, context.width - 20, y, color=value_color, scale=1)
            elif setting_key and setting_type == "slider":
                # Get slider config and current value
                config = self.slider_configs.get(setting_key)
                if config:
                    current_value = context.settings.get(setting_key, config.min_value)
                    value_str = config.format_value(current_value)

                    # Show left/right arrows if selected
                    if i == selected_idx:
                        renderer.draw_text("<", context.width - 35, y, color=(150, 150, 150), scale=1)
                        renderer.draw_text(">", context.width - 5, y, color=(150, 150, 150), scale=1)

                    renderer.draw_text(value_str, context.width - 28, y, color=(100, 200, 255), scale=1)

        # Draw scrollbar if needed
        if len(self.options) > visible_items:
            renderer.draw_scrollbar(
                x=context.width - 3,
                y=header_height,
                height=available_height,
                position=self.list.scroll_offset,
                total_items=len(self.options),
                visible_items=visible_items
            )

    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        if key == 'up':
            self.list.move_up()
        elif key == 'down':
            self.list.move_down()
        elif key in ('left', 'right'):
            # Handle slider adjustments
            selected = self.list.get_selected()
            if selected:
                label, setting_key, setting_type = selected

                if setting_type == "slider" and setting_key:
                    config = self.slider_configs.get(setting_key)
                    if config:
                        # Get current value (use min as default)
                        current_value = context.settings.get(setting_key, config.min_value)

                        # Increment or decrement
                        if key == 'right':
                            new_value = config.increment_value(current_value)
                        else:  # left
                            new_value = config.decrement_value(current_value)

                        # Update setting
                        context.settings[setting_key] = new_value
        elif key == 'enter':
            selected = self.list.get_selected()
            if selected:
                label, setting_key, setting_type = selected

                if label == "BACK TO MAIN":
                    return BackAction()
                elif setting_type == "toggle" and setting_key:
                    # Toggle boolean setting
                    context.settings[setting_key] = not context.settings.get(setting_key, False)

        elif key in ('back', 'escape'):
            return BackAction()

        return None