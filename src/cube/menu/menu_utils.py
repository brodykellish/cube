"""
Reusable menu utilities for rendering scrollable lists and UI elements.
"""

from typing import List, Tuple, Optional, Any, Dict
from dataclasses import dataclass
from .menu_renderer import MenuRenderer
from .menu_context import MenuContext


@dataclass
class SliderConfig:
    """
    Configuration for a numeric slider setting with left/right adjustment.

    This is a reusable utility for settings that need to be adjusted with
    arrow keys. It handles value clamping, increments, and display formatting.

    Example usage:
        brightness_config = SliderConfig(
            min_value=10.0,
            max_value=90.0,
            increment=5.0,
            format_string="{:.0f}%"
        )

        # Increment value (right arrow)
        new_value = brightness_config.increment_value(current_value)

        # Decrement value (left arrow)
        new_value = brightness_config.decrement_value(current_value)

        # Display value
        display_text = brightness_config.format_value(current_value)
    """
    min_value: float
    max_value: float
    increment: float
    format_string: str = "{:.1f}"  # Default format for display

    def clamp(self, value: float) -> float:
        """Clamp value to valid range."""
        return max(self.min_value, min(self.max_value, value))

    def increment_value(self, value: float) -> float:
        """Increment value by step, clamped to range."""
        return self.clamp(value + self.increment)

    def decrement_value(self, value: float) -> float:
        """Decrement value by step, clamped to range."""
        return self.clamp(value - self.increment)

    def format_value(self, value: float) -> str:
        """Format value for display."""
        return self.format_string.format(value)


class ScrollableList:
    """
    Manages scrolling state for a list of items.

    This handles scroll offset calculation and renders items with selection highlighting.
    """

    def __init__(self, items: List[Any], item_height: int = 7):
        """
        Initialize scrollable list.

        Args:
            items: List of items to display
            item_height: Height of each item in pixels
        """
        self.items = items
        self.item_height = item_height
        self.selected = 0
        self.scroll_offset = 0

    def set_items(self, items: List[Any]):
        """Update the list of items."""
        self.items = items
        self.selected = min(self.selected, max(0, len(items) - 1))
        self._update_scroll()

    def move_up(self):
        """Move selection up."""
        if self.items:
            self.selected = max(0, self.selected - 1)
            self._update_scroll()

    def move_down(self):
        """Move selection down."""
        if self.items:
            self.selected = min(len(self.items) - 1, self.selected + 1)
            self._update_scroll()

    def get_selected(self) -> Optional[Any]:
        """Get currently selected item."""
        if self.items and 0 <= self.selected < len(self.items):
            return self.items[self.selected]
        return None

    def get_selected_index(self) -> int:
        """Get currently selected index."""
        return self.selected

    def _update_scroll(self):
        """Update scroll offset to keep selected item visible (called internally)."""
        # This will be calculated during render based on available height
        pass

    def render(self, renderer: MenuRenderer, context: MenuContext,
               y_start: int, available_height: int,
               format_item: callable = None,
               selected_color: Tuple[int, int, int] = (255, 255, 100),
               normal_color: Tuple[int, int, int] = (200, 200, 200)):
        """
        Render the scrollable list.

        Args:
            renderer: Menu renderer instance
            context: Menu context with display dimensions
            y_start: Y position to start rendering
            available_height: Available vertical space
            format_item: Optional function to format item for display (item -> str)
            selected_color: Color for selected item
            normal_color: Color for unselected items
        """
        if not self.items:
            return

        # Calculate visible items
        visible_items = available_height // self.item_height

        # Update scroll offset to keep selected item visible
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        elif self.selected >= self.scroll_offset + visible_items:
            self.scroll_offset = self.selected - visible_items + 1

        # Ensure scroll offset is valid
        self.scroll_offset = max(0, min(self.scroll_offset, max(0, len(self.items) - visible_items)))

        # Render visible items
        for i in range(self.scroll_offset, min(len(self.items), self.scroll_offset + visible_items)):
            item = self.items[i]
            y = y_start + (i - self.scroll_offset) * self.item_height

            # Format item text
            if format_item:
                text = format_item(item)
            else:
                text = str(item)

            # Truncate to fit width
            max_chars = (context.width - 15) // 4
            text = text[:max_chars]

            # Render item
            color = selected_color if i == self.selected else normal_color
            renderer.draw_text(text, 10, y, color=color, scale=1)

            # Draw selection arrow
            if i == self.selected:
                renderer.draw_text(">", 2, y, color=selected_color, scale=1)

        # Draw scrollbar if needed
        if len(self.items) > visible_items:
            renderer.draw_scrollbar(
                x=context.width - 3,
                y=y_start,
                height=available_height,
                position=self.scroll_offset,
                total_items=len(self.items),
                visible_items=visible_items
            )


class MenuHeader:
    """Helper for rendering consistent menu headers."""

    @staticmethod
    def render(renderer: MenuRenderer, title: str, subtitle: str = None,
               title_color: Tuple[int, int, int] = (100, 200, 255),
               subtitle_color: Tuple[int, int, int] = (150, 150, 150)) -> int:
        """
        Render menu header with title and optional subtitle.

        Args:
            renderer: Menu renderer instance
            title: Main title text
            subtitle: Optional subtitle text
            title_color: Title color
            subtitle_color: Subtitle color

        Returns:
            Height of rendered header (for positioning content below)
        """
        renderer.draw_text(title, 0, y=2, color=title_color, scale=1)

        if subtitle:
            renderer.draw_text(subtitle, 0, y=8, color=subtitle_color, scale=1)
            return 15

        return 10
