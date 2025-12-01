"""
Menu state classes for cube control interface.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from .menu_renderer import MenuRenderer


class MenuState(ABC):
    """Abstract base class for menu states."""

    @abstractmethod
    def render(self, renderer: MenuRenderer):
        """Render this menu state."""
        pass

    @abstractmethod
    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """
        Handle input for this menu state.

        Args:
            key: Input key name ('up', 'down', 'enter', 'back', etc.)

        Returns:
            Name of next state to transition to, or None to stay in current state
        """
        pass


class MainMenu(MenuState):
    """Main menu - select between Visualize and Settings."""

    def __init__(self):
        self.options = [
            ("VISUALIZE", "visualization_mode"),
            ("SETTINGS", "settings"),
            ("EXIT", "quit"),
        ]
        self.selected = 0

    def render(self, renderer: MenuRenderer):
        """Render main menu."""
        renderer.clear((0, 0, 10))  # Dark blue background

        # Use fixed scale to ensure text fits on all resolutions
        scale = 1

        # Title
        title_y = 2 * scale
        renderer.draw_text_centered("CUBE CONTROL", y=title_y, color=(100, 200, 255), scale=scale)

        # Menu options - centered vertically
        item_height = 7 * scale
        total_height = len(self.options) * item_height
        y_start = (renderer.height - total_height) // 2

        for i, (label, _) in enumerate(self.options):
            y = y_start + i * item_height
            color = (255, 255, 100) if i == self.selected else (200, 200, 200)

            # Draw option text (left-aligned)
            text_x = 10 * scale
            renderer.draw_text(label, text_x, y, color=color, scale=scale)

            # Draw selector arrow to the left of text
            if i == self.selected:
                arrow_x = 2 * scale
                renderer.draw_text(">", arrow_x, y, color=(255, 255, 100), scale=scale)

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """Handle main menu input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.options) - 1, self.selected + 1)
        elif key == 'enter':
            # Return the state name to transition to
            return self.options[self.selected][1]
        elif key in ('quit', 'escape'):
            return 'quit'

        return None


class ShaderBrowser(MenuState):
    """Shader browser menu - select a shader to visualize."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.shaders = []
        self.selected = 0
        self.scroll_offset = 0

        # Load shader list
        self._load_shaders()

    def _load_shaders(self):
        """Scan for available shaders."""
        shader_dirs = [
            Path("shaders"),
            Path.cwd() / "shaders",
        ]

        for shader_dir in shader_dirs:
            if shader_dir.exists() and shader_dir.is_dir():
                self.shaders = sorted(shader_dir.glob("*.glsl"))
                break

    def render(self, renderer: MenuRenderer):
        """Render shader browser."""
        renderer.clear((0, 0, 10))  # Dark blue background

        # Use fixed scale to ensure text fits on all resolutions
        scale = 1

        # Title
        title_y = 1 * scale
        renderer.draw_text_centered("SHADER SELECT", y=title_y, color=(100, 200, 255), scale=scale)

        if not self.shaders:
            error_y = renderer.height // 2
            renderer.draw_text_centered("NO SHADERS FOUND", y=error_y, color=(255, 100, 100), scale=scale)
            return

        # Calculate item height and visible items based on screen size
        item_height = 7 * scale
        y_start = 8 * scale
        available_height = renderer.height - y_start - (2 * scale)  # Minimal bottom margin
        visible_items = max(3, available_height // item_height)

        # Calculate scroll offset to keep selected item visible
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        elif self.selected >= self.scroll_offset + visible_items:
            self.scroll_offset = self.selected - visible_items + 1

        # Draw shader list
        for i in range(self.scroll_offset, min(self.scroll_offset + visible_items, len(self.shaders))):
            shader = self.shaders[i]
            list_index = i - self.scroll_offset
            y = y_start + list_index * item_height

            # Highlight if selected
            if i == self.selected:
                renderer.draw_rect(2 * scale, y - scale, renderer.width - 4 * scale, item_height - scale,
                                 color=(30, 50, 100), filled=True)

            # Draw selector arrow
            if i == self.selected:
                renderer.draw_text(">", 3 * scale, y, color=(255, 255, 100), scale=scale)

            # Draw shader name (truncate if too long)
            shader_name = shader.stem
            char_width = 4 * scale  # 3x5 font: 3 pixels + 1 spacing
            max_chars = (renderer.width - 15 * scale) // char_width
            if len(shader_name) > max_chars:
                shader_name = shader_name[:max_chars - 2] + ".."

            color = (255, 255, 100) if i == self.selected else (200, 200, 200)
            renderer.draw_text(shader_name, 11 * scale, y, color=color, scale=scale)

        # Draw scrollbar if needed
        if len(self.shaders) > visible_items:
            renderer.draw_scrollbar(
                x=renderer.width - 3 * scale,
                y=y_start,
                height=visible_items * item_height,
                position=self.scroll_offset,
                total_items=len(self.shaders),
                visible_items=visible_items,
                color=(150, 150, 150)
            )

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """Handle shader browser input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.shaders) - 1, self.selected + 1)
        elif key == 'enter':
            # Go to camera mode selection
            if self.shaders:
                selected_shader = str(self.shaders[self.selected])
                return f'camera_select:{selected_shader}'
        elif key in ('back', 'escape'):
            return 'main'

        return None


class CameraModeSelect(MenuState):
    """Camera mode selection menu - choose camera for shader."""

    def __init__(self, shader_path: str):
        """
        Initialize camera mode selection menu.

        Args:
            shader_path: Path to shader file that will be visualized
        """
        self.shader_path = shader_path
        self.options = [
            ("STATIC", "static", "No camera movement"),
            ("SPHERICAL", "spherical", "Orbit around origin"),
            ("FPS", "fps", "First-person (coming soon)"),
            ("BACK", None, None),
        ]
        self.selected = 1  # Default to spherical

    def render(self, renderer: MenuRenderer):
        """Render camera mode selection menu."""
        renderer.clear((0, 0, 10))  # Dark blue background

        scale = 1

        # Title
        title_y = 1 * scale
        renderer.draw_text_centered("CAMERA MODE", y=title_y, color=(100, 200, 255), scale=scale)

        # Show shader name
        shader_name = Path(self.shader_path).stem
        shader_y = 8 * scale
        max_chars = (renderer.width - 10 * scale) // (4 * scale)  # 3x5 font: 4 pixels per char
        if len(shader_name) > max_chars:
            shader_name = shader_name[:max_chars - 2] + ".."
        renderer.draw_text_centered(shader_name, y=shader_y, color=(150, 150, 150), scale=scale)

        # Menu options
        item_height = 7 * scale
        y_start = 16 * scale

        for i, (label, mode, description) in enumerate(self.options):
            y = y_start + i * item_height
            is_selected = (i == self.selected)

            # Highlight selected
            if is_selected and mode is not None:
                renderer.draw_rect(
                    5 * scale, y - scale,
                    renderer.width - 10 * scale, item_height - 2 * scale,
                    color=(30, 50, 100), filled=True
                )

            # Draw selector arrow
            if is_selected:
                renderer.draw_text(">", 7 * scale, y, color=(255, 255, 100), scale=scale)

            # Draw option label
            color = (255, 255, 100) if is_selected else (200, 200, 200)
            # Gray out FPS (not implemented yet)
            if mode == "fps":
                color = (100, 100, 100)

            renderer.draw_text(label, 15 * scale, y, color=color, scale=scale)

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """Handle camera mode selection input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.options) - 1, self.selected + 1)
        elif key == 'enter':
            label, mode, _ = self.options[self.selected]

            if mode is None:  # Back option
                return 'surface_browser'  # Return to shader browser
            elif mode == "fps":
                # Not implemented yet - stay in menu
                return None
            else:
                # Launch shader with selected camera mode
                return f'visualize:{self.shader_path}:{mode}'
        elif key in ('back', 'escape'):
            return 'surface_browser'  # Return to shader browser

        return None


class VisualizationModeSelect(MenuState):
    """Visualization mode selection - choose between Surface and Volume rendering."""

    def __init__(self):
        self.options = [
            ("SURFACE", "surface", "2D shader scenes"),
            ("VOLUME", "volume", "3D volumetric cube"),
            ("BACK", None, None),
        ]
        self.selected = 0

    def render(self, renderer: MenuRenderer):
        """Render visualization mode selection menu."""
        renderer.clear((0, 0, 10))  # Dark blue background

        scale = 1

        # Title
        title_y = 2 * scale
        renderer.draw_text_centered("VISUALIZATION MODE", y=title_y, color=(100, 200, 255), scale=scale)

        # Menu options
        item_height = 7 * scale
        y_start = 12 * scale

        for i, (label, mode, description) in enumerate(self.options):
            y = y_start + i * item_height
            is_selected = (i == self.selected)

            # Highlight selected
            if is_selected and mode is not None:
                renderer.draw_rect(
                    5 * scale, y - scale,
                    renderer.width - 10 * scale, item_height - 2 * scale,
                    color=(30, 50, 100), filled=True
                )

            # Draw selector arrow
            if is_selected:
                renderer.draw_text(">", 7 * scale, y, color=(255, 255, 100), scale=scale)

            # Draw option label
            color = (255, 255, 100) if is_selected else (200, 200, 200)
            renderer.draw_text(label, 15 * scale, y, color=color, scale=scale)

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """Handle visualization mode selection input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.options) - 1, self.selected + 1)
        elif key == 'enter':
            label, mode, _ = self.options[self.selected]

            if mode is None:  # Back option
                return 'main'
            elif mode == 'surface':
                return 'surface_browser'
            elif mode == 'volume':
                return 'volumetric_browser'
        elif key in ('back', 'escape'):
            return 'main'

        return None


class VolumetricShaderBrowser(MenuState):
    """Volumetric shader browser - select a volumetric shader."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.shaders = []
        self.selected = 0
        self.scroll_offset = 0

        # Load volumetric shader list
        self._load_shaders()

    def _load_shaders(self):
        """Scan for available volumetric shaders."""
        shader_dirs = [
            Path("volumetric/shaders"),
            Path.cwd() / "volumetric" / "shaders",
        ]

        for shader_dir in shader_dirs:
            if shader_dir.exists() and shader_dir.is_dir():
                self.shaders = sorted(shader_dir.glob("*.glsl"))
                break

    def render(self, renderer: MenuRenderer):
        """Render volumetric shader browser."""
        renderer.clear((0, 0, 10))  # Dark blue background

        scale = 1

        # Title
        title_y = 1 * scale
        renderer.draw_text_centered("VOLUMETRIC SHADERS", y=title_y, color=(100, 200, 255), scale=scale)

        if not self.shaders:
            error_y = renderer.height // 2
            renderer.draw_text_centered("NO VOLUMETRIC SHADERS", y=error_y, color=(255, 100, 100), scale=scale)
            return

        # Calculate item height and visible items
        item_height = 7 * scale
        y_start = 8 * scale
        available_height = renderer.height - y_start - (2 * scale)
        visible_items = max(3, available_height // item_height)

        # Calculate scroll offset
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        elif self.selected >= self.scroll_offset + visible_items:
            self.scroll_offset = self.selected - visible_items + 1

        # Draw shader list
        for i in range(self.scroll_offset, min(self.scroll_offset + visible_items, len(self.shaders))):
            shader = self.shaders[i]
            list_index = i - self.scroll_offset
            y = y_start + list_index * item_height

            # Highlight if selected
            if i == self.selected:
                renderer.draw_rect(2 * scale, y - scale, renderer.width - 4 * scale, item_height - scale,
                                 color=(30, 50, 100), filled=True)

            # Draw selector arrow
            if i == self.selected:
                renderer.draw_text(">", 3 * scale, y, color=(255, 255, 100), scale=scale)

            # Draw shader name (truncate if too long)
            shader_name = shader.stem
            char_width = 4 * scale  # 3x5 font: 4 pixels per char
            max_chars = (renderer.width - 15 * scale) // char_width
            if len(shader_name) > max_chars:
                shader_name = shader_name[:max_chars - 2] + ".."

            color = (255, 255, 100) if i == self.selected else (200, 200, 200)
            renderer.draw_text(shader_name, 11 * scale, y, color=color, scale=scale)

        # Draw scrollbar if needed
        if len(self.shaders) > visible_items:
            renderer.draw_scrollbar(
                x=renderer.width - 3 * scale,
                y=y_start,
                height=visible_items * item_height,
                position=self.scroll_offset,
                total_items=len(self.shaders),
                visible_items=visible_items,
                color=(150, 150, 150)
            )

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """Handle volumetric shader browser input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.shaders) - 1, self.selected + 1)
        elif key == 'enter':
            # Launch volumetric shader directly (no camera selection needed)
            if self.shaders:
                selected_shader = str(self.shaders[self.selected])
                return f'volumetric:{selected_shader}'
        elif key in ('back', 'escape'):
            return 'visualization_mode'

        return None


class SettingsMenu(MenuState):
    """Settings menu - configure system parameters."""

    def __init__(self, settings: dict):
        """
        Initialize settings menu.

        Args:
            settings: Shared settings dictionary (modified in-place)
        """
        self.settings = settings
        self.options = [
            ("DEBUG UI", "debug_ui", "toggle"),  # (label, setting_key, type)
            ("RESOLUTION", None, "stub"),
            ("BRIGHTNESS", None, "stub"),
            ("FPS LIMIT", None, "stub"),
            ("BACK TO MAIN", None, "exit"),
        ]
        self.selected = 0

    def render(self, renderer: MenuRenderer):
        """Render settings menu."""
        renderer.clear((0, 0, 10))  # Dark blue background

        # Use fixed scale to ensure text fits on all resolutions
        scale = 1

        # Title
        title_y = 2 * scale
        renderer.draw_text_centered("SETTINGS", y=title_y, color=(100, 200, 255), scale=scale)

        # Options
        y_start = 12 * scale
        item_height = 7 * scale

        for i, (label, setting_key, option_type) in enumerate(self.options):
            y = y_start + i * item_height

            # Determine color based on state
            if i == self.selected:
                color = (255, 255, 100)  # Yellow for selected
            elif option_type == "stub":
                color = (80, 80, 80)  # Dark gray for stub
            else:
                color = (200, 200, 200)  # Normal color

            # Draw selector arrow
            if i == self.selected:
                arrow_x = 5 * scale
                renderer.draw_text(">", arrow_x, y, color=(255, 255, 100), scale=scale)

            # Draw option label
            label_x = 15 * scale
            renderer.draw_text(label, label_x, y, color=color, scale=scale)

            # Draw option value (for toggles)
            if option_type == "toggle" and setting_key:
                value = "ON" if self.settings.get(setting_key, False) else "OFF"
                value_color = (100, 255, 100) if self.settings.get(setting_key, False) else (255, 100, 100)
                # Right-align value
                value_x = renderer.width - 30 * scale
                renderer.draw_text(value, value_x, y, color=value_color, scale=scale)
            elif option_type == "stub":
                stub_x = renderer.width - 50 * scale
                renderer.draw_text("SOON", stub_x, y, color=(80, 80, 80), scale=scale)

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """Handle settings menu input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.options) - 1, self.selected + 1)
        elif key == 'enter':
            label, setting_key, option_type = self.options[self.selected]

            if option_type == "exit":
                return 'main'
            elif option_type == "toggle" and setting_key:
                # Toggle the setting
                self.settings[setting_key] = not self.settings.get(setting_key, False)
            # Other types not yet implemented

        elif key in ('back', 'escape'):
            return 'main'

        return None
