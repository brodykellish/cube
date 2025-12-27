"""
Simple text input prompt menu state for entering filenames or other text.
"""
from typing import Optional
from .menu_states import MenuState
from .menu_context import MenuContext
from .menu_renderer import MenuRenderer
from .menu_utils import MenuHeader
from .actions import MenuAction, BackAction


class TextInputPrompt(MenuState):
    """Simple text input prompt for entering filenames."""
    
    def __init__(self, prompt_text: str, on_confirm, on_cancel=None):
        """
        Initialize text input prompt.
        
        Args:
            prompt_text: Text to display as prompt
            on_confirm: Callback function(filename: str) -> Optional[MenuAction]
            on_cancel: Optional callback function() -> Optional[MenuAction]
        """
        super().__init__('text_input_prompt')
        self.prompt_text = prompt_text
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        
        self.input_buffer = ""
        self.cursor_pos = 0
        self.cursor_visible = True
        self.cursor_blink_time = 0
    
    def render(self, renderer: MenuRenderer, context: MenuContext):
        """Render the text input prompt."""
        renderer.clear((0, 0, 0))
        
        header_height = MenuHeader.render(renderer, self.prompt_text)
        
        # Display input buffer with cursor
        input_y = header_height + 20
        input_text = self.input_buffer
        cursor_char = "|" if self.cursor_visible else " "
        
        # Insert cursor at cursor position
        if self.cursor_pos <= len(input_text):
            display_text = input_text[:self.cursor_pos] + cursor_char + input_text[self.cursor_pos:]
        else:
            display_text = input_text + cursor_char
        
        renderer.draw_text(display_text, 10, input_y, color=(200, 200, 200), scale=1)
        
        # Instructions
        renderer.draw_text("ENTER: Confirm", 10, input_y + 20, color=(150, 150, 150), scale=1)
        renderer.draw_text("ESC: Cancel", 10, input_y + 30, color=(150, 150, 150), scale=1)
    
    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        """Handle input."""
        import time
        
        # Update cursor blink
        current_time = time.time()
        if current_time - self.cursor_blink_time > 0.5:
            self.cursor_visible = not self.cursor_visible
            self.cursor_blink_time = current_time
        
        if key == 'enter':
            # Confirm input
            if self.on_confirm:
                result = self.on_confirm(self.input_buffer)
                if result:
                    return result
            return BackAction()
        elif key in ('back', 'escape'):
            # Cancel
            if self.on_cancel:
                result = self.on_cancel()
                if result:
                    return result
            return BackAction()
        elif key == 'backspace':
            # Delete character before cursor
            if self.cursor_pos > 0:
                self.input_buffer = self.input_buffer[:self.cursor_pos - 1] + self.input_buffer[self.cursor_pos:]
                self.cursor_pos -= 1
        elif key == 'delete':
            # Delete character at cursor
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = self.input_buffer[:self.cursor_pos] + self.input_buffer[self.cursor_pos + 1:]
        elif key == 'left':
            # Move cursor left
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        elif key == 'right':
            # Move cursor right
            if self.cursor_pos < len(self.input_buffer):
                self.cursor_pos += 1
        elif len(key) == 1 and key.isprintable():
            # Insert character
            self.input_buffer = self.input_buffer[:self.cursor_pos] + key + self.input_buffer[self.cursor_pos:]
            self.cursor_pos += 1
        
        return None

