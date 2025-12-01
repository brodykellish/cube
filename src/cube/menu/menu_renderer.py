"""
Menu renderer - primitive drawing operations on numpy framebuffer.
Provides simple text and shape rendering suitable for LED matrix displays.
"""

import numpy as np


# Simple 5x7 bitmap font for LED displays
# Each character is 5 pixels wide, 7 pixels tall
# Stored as a dictionary of character -> list of 7 integers (each int represents a row)
FONT_5X7 = {
    ' ': [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000],
    'A': [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    'B': [0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110],
    'C': [0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110],
    'D': [0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110],
    'E': [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111],
    'F': [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000],
    'G': [0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110],
    'H': [0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    'I': [0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    'J': [0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100],
    'K': [0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001],
    'L': [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111],
    'M': [0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001],
    'N': [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001],
    'O': [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    'P': [0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000],
    'Q': [0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101],
    'R': [0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001],
    'S': [0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110],
    'T': [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100],
    'U': [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    'V': [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
    'W': [0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001],
    'X': [0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001],
    'Y': [0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100],
    'Z': [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111],
    '0': [0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110],
    '1': [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    '2': [0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111],
    '3': [0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110],
    '4': [0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010],
    '5': [0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110],
    '6': [0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110],
    '7': [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000],
    '8': [0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110],
    '9': [0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100],
    '-': [0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000],
    ':': [0b00000, 0b00100, 0b00000, 0b00000, 0b00000, 0b00100, 0b00000],
    '/': [0b00000, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b00000],
    '>': [0b01000, 0b00100, 0b00010, 0b00001, 0b00010, 0b00100, 0b01000],
    '.': [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00100],
    '#': [0b01010, 0b11111, 0b01010, 0b01010, 0b11111, 0b01010, 0b00000],
}


class MenuRenderer:
    """Renders menu UI elements to a numpy framebuffer."""

    def __init__(self, framebuffer: np.ndarray):
        """
        Initialize menu renderer.

        Args:
            framebuffer: numpy array of shape (height, width, 3), dtype=uint8
        """
        self.framebuffer = framebuffer
        self.height, self.width = framebuffer.shape[:2]

    def clear(self, color=(0, 0, 0)):
        """Clear the framebuffer to a solid color."""
        self.framebuffer[:, :] = color

    def draw_rect(self, x, y, width, height, color, filled=True):
        """
        Draw a rectangle.

        Args:
            x, y: Top-left corner
            width, height: Dimensions
            color: RGB tuple (0-255)
            filled: If True, fill the rectangle; if False, draw outline only
        """
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(self.width, x + width), min(self.height, y + height)

        if filled:
            self.framebuffer[y1:y2, x1:x2] = color
        else:
            # Draw outline
            if y1 < self.height:
                self.framebuffer[y1, x1:x2] = color  # Top
            if y2 - 1 >= 0:
                self.framebuffer[y2 - 1, x1:x2] = color  # Bottom
            if x1 < self.width:
                self.framebuffer[y1:y2, x1] = color  # Left
            if x2 - 1 >= 0:
                self.framebuffer[y1:y2, x2 - 1] = color  # Right

    def draw_char(self, char, x, y, color=(255, 255, 255), scale=1):
        """
        Draw a single character using bitmap font.

        Args:
            char: Character to draw
            x, y: Top-left position
            color: RGB tuple (0-255)
            scale: Scaling factor (1 = 5x7 pixels)

        Returns:
            Width of the drawn character
        """
        char = char.upper()
        if char not in FONT_5X7:
            char = ' '

        bitmap = FONT_5X7[char]

        for row_idx, row_data in enumerate(bitmap):
            for col_idx in range(5):
                if row_data & (1 << (4 - col_idx)):  # Check if pixel is set
                    # Draw pixel (or scaled block)
                    for dy in range(scale):
                        for dx in range(scale):
                            px = x + col_idx * scale + dx
                            py = y + row_idx * scale + dy
                            if 0 <= px < self.width and 0 <= py < self.height:
                                self.framebuffer[py, px] = color

        return 5 * scale + scale  # Character width + spacing

    def draw_text(self, text, x, y, color=(255, 255, 255), scale=1, center=False):
        """
        Draw text string.

        Args:
            text: String to draw
            x, y: Position (top-left or center depending on center flag)
            color: RGB tuple (0-255)
            scale: Scaling factor
            center: If True, center text horizontally around x

        Returns:
            Total width of drawn text
        """
        if center:
            # Calculate total width without drawing (each char is 5 pixels + 1 spacing)
            char_width = 6 * scale
            total_width = len(text) * char_width
            x = x - total_width // 2

        cursor_x = x
        for char in text:
            cursor_x += self.draw_char(char, cursor_x, y, color, scale)

        return cursor_x - x

    def draw_text_centered(self, text, y, color=(255, 255, 255), scale=1):
        """Draw text centered horizontally."""
        x = self.width // 2
        return self.draw_text(text, x, y, color, scale, center=True)

    def draw_line(self, x1, y1, x2, y2, color=(255, 255, 255)):
        """
        Draw a line using Bresenham's algorithm.

        Args:
            x1, y1: Start point
            x2, y2: End point
            color: RGB tuple (0-255)
        """
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            if 0 <= x1 < self.width and 0 <= y1 < self.height:
                self.framebuffer[y1, x1] = color

            if x1 == x2 and y1 == y2:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def draw_scrollbar(self, x, y, height, position, total_items, visible_items, color=(128, 128, 128)):
        """
        Draw a scrollbar.

        Args:
            x, y: Top-left corner
            height: Total scrollbar height
            position: Current scroll position (0-based)
            total_items: Total number of items
            visible_items: Number of visible items
            color: RGB tuple (0-255)
        """
        if total_items <= visible_items:
            return  # No scrollbar needed

        # Draw scrollbar track
        self.draw_rect(x, y, 2, height, (50, 50, 50), filled=True)

        # Calculate handle size and position
        handle_height = max(3, int(height * visible_items / total_items))
        handle_y = y + int((height - handle_height) * position / max(1, total_items - visible_items))

        # Draw handle
        self.draw_rect(x, handle_y, 2, handle_height, color, filled=True)
