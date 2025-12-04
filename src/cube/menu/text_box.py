"""
Scrollable text box with word wrapping.

Displays text content in a scrollable box with automatic word wrapping
and line number support. Suitable for showing prompts, responses, logs, etc.
"""

import numpy as np
from typing import List, Tuple


class TextBox:
    """
    Scrollable text box with word wrapping.

    Handles text display, word wrapping, and scrolling within a bounded region.
    """

    def __init__(self, x: int, y: int, width: int, height: int,
                 fg_color: Tuple[int, int, int] = (200, 200, 200),
                 bg_color: Tuple[int, int, int] = (0, 0, 0)):
        """
        Initialize text box.

        Args:
            x: X position (pixels)
            y: Y position (pixels)
            width: Box width (pixels)
            height: Box height (pixels)
            fg_color: Foreground (text) color RGB
            bg_color: Background color RGB
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.fg_color = fg_color
        self.bg_color = bg_color

        # Text content
        self.lines: List[str] = []
        self.line_types: List[str] = []  # Track line types: 'user', 'cube', 'cube_cont', 'other'
        self.scroll_offset = 0

        # Character dimensions (must match MenuRenderer.draw_text at scale=1)
        self.char_width = 4  # Actual character width: 3 pixels + 1 spacing
        self.char_height = 8  # Reduced from 10
        self.line_spacing = 1  # Reduced from 2

        # Calculate visible dimensions
        self.chars_per_line = max(1, (width - 8) // self.char_width)  # 4px padding each side
        self.visible_lines = max(1, (height - 8) // (self.char_height + self.line_spacing))

    def set_text(self, text: str):
        """
        Set text content with automatic word wrapping.

        Args:
            text: Text content (may contain newlines)
        """
        self.lines = []
        self.line_types = []

        # Split by newlines first
        paragraphs = text.split('\n')

        for paragraph in paragraphs:
            if not paragraph.strip():
                # Empty line
                self.lines.append('')
                self.line_types.append('empty')
                continue

            # Detect message type and extract prefix
            prefix = ''
            indent = ''
            content_start = 0
            line_type = 'other'
            continuation_type = 'other'

            if paragraph.startswith('user: '):
                prefix = 'user: '
                content_start = 6
                indent = '  '  # 2-char indent for wrapped lines (matches cube style)
                line_type = 'user'
                continuation_type = 'user_cont'
            elif paragraph.startswith('cube: '):
                prefix = 'cube: '
                content_start = 6
                indent = '  '  # 2-char indent for wrapped lines
                line_type = 'cube'
                continuation_type = 'cube_cont'

            # Get the actual content (without prefix)
            content = paragraph[content_start:] if content_start > 0 else paragraph

            # Word wrap this paragraph
            words = content.split(' ')
            current_line = prefix  # Start with prefix on first line
            is_first_line = True

            for word in words:
                # Determine if we need a space before this word
                need_space = current_line and current_line != prefix and current_line != indent
                test_line = current_line + (' ' if need_space else '') + word

                if len(test_line) <= self.chars_per_line:
                    current_line = test_line
                else:
                    # Current line is full, start new line
                    if current_line:
                        self.lines.append(current_line)
                        self.line_types.append(line_type if is_first_line else continuation_type)
                        is_first_line = False

                    # Start new line with indent (for continuation) or just the word
                    if not is_first_line:
                        # Continuation line - use indent
                        # Handle very long words (break mid-word)
                        if len(word) > self.chars_per_line - len(indent):
                            # Split long word across multiple lines with indent
                            while len(word) > self.chars_per_line - len(indent):
                                self.lines.append(indent + word[:self.chars_per_line - len(indent)])
                                self.line_types.append(continuation_type)
                                word = word[self.chars_per_line - len(indent):]
                            current_line = indent + word
                        else:
                            current_line = indent + word
                    else:
                        # First line wrapping - shouldn't happen if prefix already added
                        current_line = word

            # Add remaining content
            if current_line and current_line != prefix and current_line != indent:
                self.lines.append(current_line)
                self.line_types.append(line_type if is_first_line else continuation_type)

        # Reset scroll to bottom
        self.scroll_to_bottom()

    def append_text(self, text: str):
        """
        Append text to existing content.

        Args:
            text: Text to append
        """
        current_text = '\n'.join(self.lines)
        if current_text:
            current_text += '\n'
        current_text += text
        self.set_text(current_text)

    def scroll_up(self, lines: int = 1):
        """Scroll up by specified number of lines."""
        self.scroll_offset = max(0, self.scroll_offset - lines)

    def scroll_down(self, lines: int = 1):
        """Scroll down by specified number of lines."""
        max_offset = max(0, len(self.lines) - self.visible_lines)
        self.scroll_offset = min(max_offset, self.scroll_offset + lines)

    def scroll_to_top(self):
        """Scroll to top of content."""
        self.scroll_offset = 0

    def scroll_to_bottom(self):
        """Scroll to bottom of content."""
        self.scroll_offset = max(0, len(self.lines) - self.visible_lines)

    def update_dimensions(self, x: int = None, y: int = None, width: int = None, height: int = None):
        """
        Update text box dimensions and recalculate visible lines.

        Args:
            x: New X position (optional)
            y: New Y position (optional)
            width: New width (optional)
            height: New height (optional)
        """
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if width is not None:
            self.width = width
            self.chars_per_line = max(1, (width - 8) // self.char_width)
        if height is not None:
            self.height = height
            self.visible_lines = max(1, (height - 8) // (self.char_height + self.line_spacing))

    def render(self, surface: np.ndarray):
        """
        Render text box to surface.

        Args:
            surface: NumPy array (height, width, 3) to render into
        """
        # Draw background
        surface[self.y:self.y + self.height, self.x:self.x + self.width] = self.bg_color

        # Recalculate visible lines in case height changed
        old_visible = self.visible_lines
        self.visible_lines = max(1, (self.height - 4) // (self.char_height + self.line_spacing))

        # If visible lines changed and we were at the bottom, stay at the bottom
        if old_visible != self.visible_lines:
            max_offset = max(0, len(self.lines) - old_visible)
            if self.scroll_offset >= max_offset - 1:  # Was at or near bottom
                self.scroll_to_bottom()

        # Clamp scroll offset to valid range
        max_offset = max(0, len(self.lines) - self.visible_lines)
        self.scroll_offset = min(self.scroll_offset, max_offset)

        # Calculate visible line range
        start_line = self.scroll_offset
        end_line = min(len(self.lines), start_line + self.visible_lines)

        # Render visible lines using actual text rendering with color coding
        # Import MenuRenderer here to avoid circular imports
        from .menu_renderer import MenuRenderer

        renderer = MenuRenderer(surface)
        text_y = self.y + 2  # Minimal padding

        for i in range(start_line, end_line):
            line = self.lines[i]
            line_type = self.line_types[i] if i < len(self.line_types) else 'other'
            text_x = self.x + 2  # Minimal padding

            # Render text using MenuRenderer with color coding
            if line:  # Only render non-empty lines
                if line_type == 'cube':
                    # Cube message first line - render prefix in blue, rest in white
                    # Render "cube: " in blue
                    renderer.draw_text('cube: ', text_x, text_y, color=(100, 200, 255), scale=1)
                    # Render rest of message in white (offset by prefix width)
                    rest_of_message = line[6:]  # After "cube: "
                    prefix_width = 6 * 4  # 6 chars * 4 pixels per char
                    renderer.draw_text(rest_of_message, text_x + prefix_width, text_y, color=(200, 200, 200), scale=1)
                elif line_type == 'cube_cont':
                    # Continuation line of cube message - render in white
                    renderer.draw_text(line, text_x, text_y, color=(200, 200, 200), scale=1)
                elif line_type == 'user':
                    # User message first line - render prefix in red, rest in white
                    # Render "user: " in red
                    renderer.draw_text('user: ', text_x, text_y, color=(255, 80, 80), scale=1)
                    # Render rest of message in white (offset by prefix width)
                    rest_of_message = line[6:]  # After "user: "
                    prefix_width = 6 * 4  # 6 chars * 4 pixels per char
                    renderer.draw_text(rest_of_message, text_x + prefix_width, text_y, color=(200, 200, 200), scale=1)
                elif line_type == 'user_cont':
                    # Continuation line of user message - render in white with indentation
                    renderer.draw_text(line, text_x, text_y, color=(200, 200, 200), scale=1)
                else:
                    # Default color
                    renderer.draw_text(line, text_x, text_y, color=self.fg_color, scale=1)

            text_y += self.char_height + self.line_spacing

            if text_y >= self.y + self.height - 2:
                break


def wrap_text(text: str, max_line_length: int) -> List[str]:
    """
    Wrap text to specified line length with word boundaries.

    Args:
        text: Text to wrap
        max_line_length: Maximum characters per line

    Returns:
        List of wrapped lines
    """
    lines = []
    paragraphs = text.split('\n')

    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append('')
            continue

        words = paragraph.split(' ')
        current_line = ''

        for word in words:
            test_line = current_line + (' ' if current_line else '') + word

            if len(test_line) <= max_line_length:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)

                if len(word) > max_line_length:
                    while len(word) > max_line_length:
                        lines.append(word[:max_line_length])
                        word = word[max_line_length:]
                    current_line = word
                else:
                    current_line = word

        if current_line:
            lines.append(current_line)

    return lines
