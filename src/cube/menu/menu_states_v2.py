"""
Refactored menu states using clean action-based system.
"""

from pathlib import Path
from typing import Optional, List, Tuple
from abc import ABC, abstractmethod
from .actions import (
    MenuAction, NavigateAction, BackAction, QuitAction,
    LaunchVisualizationAction, ShowRenderModeMenuAction
)
from .navigation import MenuContext
from .menu_renderer import MenuRenderer
from .menu_utils import ScrollableList, MenuHeader, SliderConfig
from cube.shader.template_engine import ShaderTemplateEngine


class MenuState(ABC):
    """Base class for all menu states."""

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
        self.options = [
            ("VISUALIZE", "visualization_mode"),
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
                elif target:
                    return NavigateAction(target=target)
        elif key in ('back', 'escape'):
            return QuitAction()
        return None


class VisualizationModeSelect(MenuState):
    """Select between Surface and Cube rendering modes."""

    def __init__(self):
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
    """Browse and select shaders for visualization with categories."""

    def __init__(self, pixel_mapper: str):
        """
        Initialize shader browser.

        Args:
            pixel_mapper: 'surface' or 'cube' - determines how shader will be rendered
        """
        self.pixel_mapper = pixel_mapper
        self.template_engine = ShaderTemplateEngine()

        # Build combined list: categories as headers, items as selectable entries
        self.items = []  # List of tuples: (type, name, data)
        self.list = ScrollableList(self.items)  # Create list first
        self._load_all_items()  # Then populate it

    def _load_all_items(self):
        """Load primitives and graphics shaders into categorized list."""
        self.items = []

        # Add primitives category
        primitives = self.template_engine.list_primitives()
        if primitives:
            self.items.append(("category", "PRIMITIVES", None))
            for primitive in primitives:
                self.items.append(("primitive", primitive, primitive))

        # Add graphics category
        shader_dir = Path("shaders")
        graphics_shaders = []
        if shader_dir.exists():
            graphics_shaders = sorted(shader_dir.glob("*.glsl"))

        if graphics_shaders:
            self.items.append(("category", "GRAPHICS", None))
            for shader_path in graphics_shaders:
                self.items.append(("shader", shader_path.stem, shader_path))

        # Add back option
        self.items.append(("action", "BACK", None))

        self.list.set_items(self.items)

        # Skip to first selectable item (skip category headers)
        if self.items and self.items[0][0] == "category":
            self.list.move_down()

    def render(self, renderer: MenuRenderer, context: MenuContext):
        renderer.clear((0, 0, 0))

        # Header
        title = "SELECT SHADER"
        subtitle = f"[{self.pixel_mapper.upper()}]"
        header_height = MenuHeader.render(renderer, title, subtitle)

        if not self.items:
            renderer.draw_text("NO SHADERS FOUND", 0, y=header_height, color=(255, 100, 100), scale=1)
            return

        # Calculate available space
        available_height = context.height - header_height

        # Custom render function that handles categories
        def format_item(item):
            item_type, name, _ = item
            if item_type == "category":
                return f"--- {name} ---"
            elif item_type == "primitive":
                return f"  {name.upper()}"
            elif item_type == "shader":
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
            # Skip category headers
            while self.list.get_selected() and self.list.get_selected()[0] == "category":
                if self.list.get_selected_index() > 0:
                    self.list.move_up()
                else:
                    break
        elif key == 'down':
            self.list.move_down()
            # Skip category headers
            while self.list.get_selected() and self.list.get_selected()[0] == "category":
                if self.list.get_selected_index() < len(self.list.items) - 1:
                    self.list.move_down()
                else:
                    break
        elif key == 'enter':
            selected = self.list.get_selected()
            if selected:
                item_type, name, data = selected

                if item_type == "primitive":
                    # Generate shader from primitive
                    return LaunchVisualizationAction(
                        shader_path=None,
                        pixel_mapper=self.pixel_mapper,
                        primitive=data
                    )
                elif item_type == "shader":
                    # Load graphics shader
                    return LaunchVisualizationAction(
                        shader_path=data,
                        pixel_mapper=self.pixel_mapper
                    )
                elif item_type == "action" and name == "BACK":
                    return BackAction()
        elif key in ('back', 'escape'):
            return BackAction()
        return None


class SettingsMenu(MenuState):
    """Settings menu for system configuration."""

    def __init__(self):
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