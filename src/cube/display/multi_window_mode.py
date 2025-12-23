"""
Multi-Window Display Mode - Three separate windows.

Splits display into:
1. Main visualization window (pygame - shader + effects)
2. Menu window (tkinter - always visible, non-blocking)
3. Debug window (tkinter - toggleable, shows parameters)
"""
import numpy as np
import pygame
import tkinter as tk
from PIL import Image, ImageTk
from typing import Tuple, Optional
from .display_mode import DisplayMode


class MultiWindowMode(DisplayMode):
    """
    Three separate windows for visualization, menu, and debug.

    Uses pygame for main viz, tkinter for menu/debug.
    """

    def __init__(self, width: int, height: int, scale: int=1, **kwargs):
        """
        Initialize multi-window mode.

        Args:
            width: Main visualization width
            height: Main visualization height
            scale: Display scale factor
            **kwargs: Additional arguments (ignored)
        """
        self.width = width
        self.height = height
        self.scale = scale
        self.debug_visible = False
        
        if not pygame.get_init():
            pygame.init()
        
        print('[MultiWindow] Creating main visualization window...')
        import os
        os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'
        self.main_surface = pygame.display.set_mode((width * scale, height * scale), pygame.RESIZABLE)
        pygame.display.set_caption('Cube Visualization')
        
        print('[MultiWindow] Creating menu window...')
        self.tk_root = tk.Tk()
        self.tk_root.title('Cube Menu')
        self.tk_root.geometry('512x400+650+100')
        self.tk_root.configure(bg='black')
        self.menu_canvas = tk.Canvas(self.tk_root, width=512, height=400, bg='black', highlightthickness=0)
        self.menu_canvas.pack()
        self.menu_photo_image = None
        
        print('[MultiWindow] Creating debug window...')
        self.debug_window = tk.Toplevel(self.tk_root)
        self.debug_window.title('Debug Panel')
        self.debug_window.geometry('800x600+1200+100')
        self.debug_window.configure(bg='black')
        self.debug_window.withdraw()
        self.debug_canvas = tk.Canvas(self.debug_window, width=800, height=600, bg='black', highlightthickness=0)
        self.debug_canvas.pack()
        self.debug_photo_image = None
        
        print('Multi-window mode initialized:')
        print(f'  Main: {width}×{height} (scale {scale})')
        print('  Menu: 512×400')
        print('  Debug: 800×600 (hidden)')

    def show_visualization(self, framebuffer: np.ndarray, brightness: float, gamma: float):
        """Display visualization in main pygame window."""
        corrected = self._apply_corrections(framebuffer, brightness, gamma)
        surf = pygame.surfarray.make_surface(np.transpose(corrected, (1, 0, 2)))
        if self.scale != 1:
            surf = pygame.transform.scale(surf, (corrected.shape[1] * self.scale, corrected.shape[0] * self.scale))
        self.main_surface.blit(surf, (0, 0))
        pygame.display.flip()

    def show_menu(self, menu_layer: np.ndarray):
        """Display menu in tkinter window."""
        try:
            img = Image.fromarray(menu_layer, mode='RGB')
            self.menu_photo_image = ImageTk.PhotoImage(image=img)
            self.menu_canvas.delete('all')
            self.menu_canvas.create_image(0, 0, anchor=tk.NW, image=self.menu_photo_image)
        except Exception:
            pass

    def show_debug(self, debug_layer: np.ndarray):
        """Display debug in tkinter window (if visible)."""
        if not self.debug_visible:
            return
        try:
            img = Image.fromarray(debug_layer, mode='RGB')
            self.debug_photo_image = ImageTk.PhotoImage(image=img)
            self.debug_canvas.delete('all')
            self.debug_canvas.create_image(0, 0, anchor=tk.NW, image=self.debug_photo_image)
        except Exception:
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
        """Handle events from both pygame and tkinter windows."""
        result = {'quit': False, 'key': None}
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                result['quit'] = True
            elif event.type == pygame.KEYDOWN:
                result['key'] = self._map_pygame_key(event)
        
        try:
            self.tk_root.update()
        except tk.TclError:
            result['quit'] = True
        
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
        """
        In multi-window mode, visualization always processes input.
        Menu is separate window with its own input.
        """
        return False

    def toggle_debug_window(self):
        """Toggle debug window visibility."""
        self.debug_visible = not self.debug_visible
        if self.debug_visible:
            self.debug_window.deiconify()
            print('Debug window shown')
        else:
            self.debug_window.withdraw()
            print('Debug window hidden')

    def cleanup(self):
        """Clean up all windows."""
        try:
            self.tk_root.destroy()
        except Exception:
            pass
        pygame.quit()
