"""
Mixer menu UI - channel setup and configuration.
"""

from typing import Optional
from pathlib import Path
from cube.menu.menu_renderer import MenuRenderer
from cube.menu.menu_states import MenuState


class MixerSetupMenu(MenuState):
    """
    Mixer setup menu - configure channels and start mixing.

    Shows list of channels with their assigned shaders.
    Extensible design for 2-8 channels.
    """

    def __init__(self, mixer_state, width: int, height: int, num_channels: int = 2):
        """
        Initialize mixer setup menu.

        Args:
            mixer_state: MixerState instance to configure
            width: Display width
            height: Display height
            num_channels: Number of channels (2-8)
        """
        self.mixer_state = mixer_state
        self.width = width
        self.height = height
        self.num_channels = num_channels

        # Build menu options
        self.options = []
        channel_ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][:num_channels]
        for channel_id in channel_ids:
            self.options.append(('CHANNEL', channel_id))

        self.options.append(('START_MIXING', None))
        self.options.append(('BACK', None))

        self.selected = 0

    def render(self, renderer: MenuRenderer):
        """Render mixer setup menu."""
        renderer.clear((0, 0, 0))  # Black background

        scale = 1

        # Title
        title_y = 2 * scale
        renderer.draw_text("MIXER SETUP", 0, y=title_y, color=(100, 200, 255), scale=scale)

        # Menu options
        item_height = 7 * scale
        y_start = 12 * scale

        for i, (option_type, channel_id) in enumerate(self.options):
            y = y_start + i * item_height
            is_selected = (i == self.selected)

            # Build label based on option type
            if option_type == 'CHANNEL':
                channel = self.mixer_state.get_channel(channel_id)
                if channel.has_shader():
                    shader_name = Path(channel.shader_path).stem
                    # Truncate if too long
                    if len(shader_name) > 15:
                        shader_name = shader_name[:13] + ".."
                    label = f"CH {channel_id}: {shader_name}"
                else:
                    label = f"CH {channel_id}: [EMPTY]"
            elif option_type == 'START_MIXING':
                # Check if at least one channel has a shader
                channel_ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][:self.num_channels]
                has_any = any(
                    self.mixer_state.get_channel(cid).has_shader()
                    for cid in channel_ids
                )
                if has_any:
                    label = "START MIXING"
                else:
                    label = "START MIXING (need shaders)"
            else:  # BACK
                label = "BACK TO MENU"

            # Color
            color = (255, 255, 100) if is_selected else (200, 200, 200)

            # Draw label
            text_x = 10 * scale
            renderer.draw_text(label, text_x, y, color=color, scale=scale)

            # Draw selector arrow
            if is_selected:
                arrow_x = 2 * scale
                renderer.draw_text(">", arrow_x, y, color=(255, 255, 100), scale=scale)

    def handle_input(self, key: Optional[str]) -> Optional[str]:
        """Handle mixer setup menu input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.options) - 1, self.selected + 1)
        elif key == 'enter':
            option_type, channel_id = self.options[self.selected]

            if option_type == 'CHANNEL':
                # Enter shader browser for this channel
                return f'mixer_shader_select:{channel_id}'
            elif option_type == 'START_MIXING':
                # Check if at least one channel has a shader
                channel_ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][:self.num_channels]
                has_any = any(
                    self.mixer_state.get_channel(cid).has_shader()
                    for cid in channel_ids
                )
                if has_any:
                    return 'mixer_start'
            elif option_type == 'BACK':
                return 'main'
        elif key in ('back', 'escape'):
            return 'main'

        return None


class MixerShaderBrowser(MenuState):
    """
    Shader browser for mixer channel.

    Similar to regular shader browser but assigns shader to a specific channel.
    """

    def __init__(self, mixer_state, channel_id: str, width: int, height: int):
        """
        Initialize mixer shader browser.

        Args:
            mixer_state: MixerState to configure
            channel_id: Channel to assign shader to ('A', 'B', etc)
            width: Display width
            height: Display height
        """
        self.mixer_state = mixer_state
        self.channel_id = channel_id
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
        """Render mixer shader browser."""
        renderer.clear((0, 0, 0))  # Black background

        scale = 1

        # Title
        title_y = 1 * scale
        renderer.draw_text(f"SELECT SHADER: CH {self.channel_id}", 0, y=title_y, color=(100, 200, 255), scale=scale)

        if not self.shaders:
            error_y = 12 * scale
            renderer.draw_text("NO SHADERS FOUND", 0, y=error_y, color=(255, 100, 100), scale=scale)
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

            # Draw selector arrow
            if i == self.selected:
                renderer.draw_text(">", 3 * scale, y, color=(255, 255, 100), scale=scale)

            # Draw shader name (truncate if too long)
            shader_name = shader.stem
            char_width = 4 * scale
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
        """Handle mixer shader browser input."""
        if key == 'up':
            self.selected = max(0, self.selected - 1)
        elif key == 'down':
            self.selected = min(len(self.shaders) - 1, self.selected + 1)
        elif key == 'enter':
            # Assign shader to channel
            if self.shaders:
                selected_shader = str(self.shaders[self.selected])
                return f'mixer_assign_shader:{self.channel_id}:{selected_shader}'
        elif key in ('back', 'escape'):
            # Return to mixer setup menu
            return 'mixer_setup'

        return None
