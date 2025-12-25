"""
Pygame display backend for development on macOS/Linux/Windows.
"""

import numpy as np
from .display_backend import DisplayBackend
from ..input.pygame_keyboard import PygameKeyboard


class PygameBackend(DisplayBackend):
    """Pygame backend for development on macOS/Linux/Windows."""

    def __init__(self, width: int, height: int, scale: int = 1, **kwargs):
        """
        Initialize pygame backend.

        Args:
            width: Window width in pixels (fixed)
            height: Window height in pixels (fixed)
            scale: Content scale factor - determines internal rendering resolution (default 1)
                   scale=2 means render at width/2 × height/2 and scale up to fit window
            **kwargs: Additional arguments (ignored, for cross-backend compatibility)
        """
        print("Creating pygame backend")
        # Internal rendering resolution (scaled down)
        internal_width = width // scale
        internal_height = height // scale
        super().__init__(internal_width, internal_height)

        import pygame
        self.pygame = pygame

        pygame.init()
        self.scale = scale
        self.window_width = width
        self.window_height = height
        self.aspect_ratio = width / height if height > 0 else 1.0
        self._ignore_aspect_ratio = False

        # Create resizable window
        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        print(f"Pygame backend initialized: {self.window_width}×{self.window_height} window (resizable), {internal_width}×{internal_height} render (scale {scale}x)")

        pygame.display.set_caption("Cube Control")

        # Initialize keyboard input handler
        self.keyboard = PygameKeyboard(pygame)
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.mouse_button_pressed = False

    def show_framebuffer(self, framebuffer: np.ndarray):
        """
        Display a complete framebuffer via pygame.

        Scales framebuffer content to fill the fixed window size.
        Uses nearest-neighbor scaling to preserve sharp pixel edges.

        Args:
            framebuffer: Complete framebuffer to display (any size)
        """
        # Convert numpy array to pygame surface
        surface = self.pygame.surfarray.make_surface(
            np.transpose(framebuffer, (1, 0, 2))
        )

        # Scale content to fill window using nearest-neighbor (no smoothing)
        # This preserves sharp pixel edges for that "chunky pixel" look
        surface = self.pygame.transform.scale(
            surface,
            (self.window_width, self.window_height)
        )

        self.screen.blit(surface, (0, 0))
        self.pygame.display.flip()

    def handle_events(self) -> dict:
        """Handle pygame events using keyboard abstraction."""
        # Get all events and filter resize events before keyboard processing
        all_events = self.pygame.event.get()
        resize_events = []
        other_events = []
        
        for event in all_events:
            if event.type == self.pygame.VIDEORESIZE:
                resize_events.append(event)
            else:
                other_events.append(event)
        
        # Handle resize events first
        for event in resize_events:
            new_width = event.w
            new_height = event.h
            print(f"Pygame backend resize event: {new_width}×{new_height}")
            if self._ignore_aspect_ratio:
                self.window_width = new_width
                self.window_height = new_height
                self.screen = self.pygame.display.set_mode((self.window_width, self.window_height), self.pygame.RESIZABLE)
                print(f"[Pygame] Window resized to {self.window_width}×{self.window_height} (aspect ratio ignored)")
                continue
            else:
                # Manual resize: maintain aspect ratio
                # Calculate which dimension changed more (relative to current size)
                width_change = abs(new_width - self.window_width) / max(self.window_width, 1)
                height_change = abs(new_height - self.window_height) / max(self.window_height, 1)
                
                # Maintain aspect ratio by using the dimension that changed more as primary
                if width_change >= height_change:
                    # Width changed more, calculate height from width
                    constrained_height = int(new_width / self.aspect_ratio)
                    self.window_width = new_width
                    self.window_height = constrained_height
                else:
                    # Height changed more, calculate width from height
                    constrained_width = int(new_height * self.aspect_ratio)
                    self.window_width = constrained_width
                    self.window_height = new_height
            
            # Recreate screen surface with constrained size
            self.screen = self.pygame.display.set_mode((self.window_width, self.window_height), self.pygame.RESIZABLE)
            print(f"[Pygame] Window resized to {self.window_width}×{self.window_height} (aspect ratio locked)")
        
        # Process remaining events for keyboard input
        # Since pygame.event.get() consumes events, we need to manually process them
        # Create a temporary event queue by monkey-patching event.get()
        original_event_get = self.pygame.event.get
        event_list = list(other_events)  # Make a copy
        
        def mock_event_get():
            """Mock event.get() that returns our filtered events."""
            nonlocal event_list
            result = event_list
            event_list = []  # Clear after first call
            return result
        
        self.pygame.event.get = mock_event_get
        
        try:
            # Poll keyboard for input (will process the non-resize events)
            keyboard_state = self.keyboard.poll()
        finally:
            # Restore original event.get()
            self.pygame.event.get = original_event_get
        
        # Get mouse state
        mouse_pos = self.pygame.mouse.get_pos()
        mouse_buttons = self.pygame.mouse.get_pressed()
        scale_x = self.width / self.window_width if self.window_width > 0 else 1.0
        scale_y = self.height / self.window_height if self.window_height > 0 else 1.0
        self.mouse_x = float(mouse_pos[0] * scale_x)
        self.mouse_y = float((self.window_height - mouse_pos[1]) * scale_y)
        self.mouse_button_pressed = mouse_buttons[0] or mouse_buttons[1] or mouse_buttons[2]

        # Convert KeyboardState to dict format
        result = {
            'quit': keyboard_state.quit,
            'key': keyboard_state.key_press,
            'keys': keyboard_state.keys_held,
            'paste': keyboard_state.paste_text,
            'mouse': {
                'x': self.mouse_x,
                'y': self.mouse_y,
                'button_pressed': self.mouse_button_pressed
            }
        }

        return result

    def cleanup(self):
        """Clean up pygame and keyboard."""
        self.keyboard.cleanup()
        self.pygame.quit()
