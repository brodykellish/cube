"""
Multi-Window Display Mode - Pure Pygame Implementation.

Uses environment variable hacks to create multiple pygame windows.
Works without tkinter dependency.
"""
import numpy as np
import pygame
import os
from typing import Tuple, Optional
from .display_mode import DisplayMode


class MultiWindowModePygame(DisplayMode):
    """
    Three pygame windows (requires SDL_VIDEO_WINDOW_POS hack).

    Main viz, menu, and debug windows all using pygame.
    """

    def __init__(self, width: int, height: int, scale: int=1, **kwargs):
        """
        Initialize multi-window pygame mode.

        Args:
            width: Main visualization width
            height: Main visualization height
            scale: Display scale factor
        """
        self.width = width
        self.height = height
        self.scale = scale
        self.debug_visible = False
        
        if not pygame.get_init():
            pygame.init()
        
        print('[MultiWindow] Creating main visualization window...')
        os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'
        self.main_surface = pygame.display.set_mode((width * scale, height * scale), pygame.RESIZABLE)
        pygame.display.set_caption('Cube Visualization')
        
        self.menu_width = 512
        self.menu_height = 400
        self.debug_width = 800
        self.debug_height = 600
        
        print('Multi-window mode (pygame) initialized:')
        print(f'  Main: {width}×{height} (scale {scale})')
        print('  Menu/Debug: Requires separate processes (not implemented)')
        print('  [Fallback: Rendering to main window only]')

    def show_visualization(self, framebuffer: np.ndarray, brightness: float, gamma: float):
        """Display visualization in main pygame window."""
        corrected = self._apply_corrections(framebuffer, brightness, gamma)
        surf = pygame.surfarray.make_surface(np.transpose(corrected, (1, 0, 2)))
        if self.scale != 1:
            surf = pygame.transform.scale(surf, (corrected.shape[1] * self.scale, corrected.shape[0] * self.scale))
        self.main_surface.blit(surf, (0, 0))
        pygame.display.flip()

    def show_menu(self, menu_layer: np.ndarray):
        """Menu rendering (TODO: separate process)."""
        pass

    def show_debug(self, debug_layer: np.ndarray):
        """Debug rendering (TODO: separate process)."""
        pass

    def _apply_corrections(self, framebuffer: np.ndarray, brightness: float, gamma: float) -> np.ndarray:
        """Apply brightness and gamma corrections."""
        result = framebuffer.astype(np.float32)
        if gamma != 1.0:
            result = np.power(result / 255.0, gamma) * 255.0
        if brightness != 100.0:
            result = result * (brightness / 100.0)
        return np.clip(result, 0, 255).astype(np.uint8)

    def handle_events(self) -> dict:
        """Handle pygame events."""
        result = {'quit': False, 'key': None}
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                result['quit'] = True
            elif event.type == pygame.KEYDOWN:
                result['key'] = self._map_pygame_key(event)
        return result

    def _map_pygame_key(self, event) -> Optional[str]:
        """Map pygame key event to key name."""
        key_map = {
            pygame.K_ESCAPE: 'escape',
            pygame.K_RETURN: 'enter',
            pygame.K_UP: 'up',
            pygame.K_DOWN: 'down',
            pygame.K_LEFT: 'left',
            pygame.K_RIGHT: 'right',
            pygame.K_BACKSLASH: '\\',
            pygame.K_MINUS: '-',
            pygame.K_UNDERSCORE: '_',
            pygame.K_EQUALS: '=',
            pygame.K_PLUS: '+',
            pygame.K_LEFTBRACKET: '[',
            pygame.K_RIGHTBRACKET: ']',
            pygame.K_SEMICOLON: ';',
            pygame.K_QUOTE: "'",
            pygame.K_COMMA: ',',
            pygame.K_PERIOD: '.',
            pygame.K_SLASH: '/'
        }
        
        if event.key in key_map:
            return key_map[event.key]
        if event.key in range(pygame.K_a, pygame.K_z + 1):
            return chr(event.key)
        if event.key in range(pygame.K_0, pygame.K_9 + 1):
            return chr(event.key)
        if event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
            return 'shift'
        
        return None

    def get_dimensions(self) -> Tuple[int, int]:
        """Get main window dimensions."""
        return (self.width, self.height)

    def is_menu_focused(self) -> bool:
        """In single-pygame mode, no separate menu focus."""
        return False

    def toggle_debug_window(self):
        """Toggle debug window (not implemented in pure pygame mode)."""
        self.debug_visible = not self.debug_visible
        print(f"Debug: {('enabled' if self.debug_visible else 'disabled')} (overlay mode in pygame-only)")

    def cleanup(self):
        """Clean up pygame."""
        pygame.quit()
