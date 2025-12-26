"""
Standalone debug renderer utility for both menu and visualization windows.

Provides reusable debug overlay rendering functionality.
"""
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from cube.menu.menu_renderer import MenuRenderer


class DebugRenderer:
    """
    Standalone debug renderer for debug pane.
    
    Provides separate methods to render different debug UI components.
    Each method returns a minimally-sized numpy array that the caller positions.
    """
    
    def __init__(self):
        """Initialize debug renderer."""
        self._beat_history: List[Tuple[float, float]] = []
        self._pygame_font = None
        self._pygame_available = False
        self._effects_scroll_offset_pygame = 0
    
    def render_effects_list(
        self,
        width: int,
        height: int,
        renderer: Optional[Any] = None,
        input_manager: Optional[Any] = None,
    ) -> np.ndarray:
        """
        Render active effects list.
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            renderer: Optional renderer instance to get effect manager
            input_manager: Optional input manager for bindings
        
        Returns:
            Numpy array (H, W, 3) with effects list rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        
        if not renderer or not hasattr(renderer, "effect_manager"):
            return result
        
        try:
            effect_manager = renderer.effect_manager
            active_actions = effect_manager.get_active_actions()
            
            if not active_actions:
                return result
            
            overlay_renderer = MenuRenderer(result)
            char_height = 12
            char_width = 6
            line_spacing = 3
            
            lines: List[str] = []
            for action in active_actions:
                friendly = action.name.replace("TOGGLE_", "").replace("_", " ").title()
                binding_text = "[unbound]"
                
                if input_manager and hasattr(input_manager, 'bindings'):
                    from cube.input.actions import InputContext
                    raw_bindings = input_manager.bindings.get_raw_inputs(
                        action, InputContext.VISUALIZATION
                    )
                    if raw_bindings:
                        labels = [self._format_binding_label(b) for b in raw_bindings]
                        binding_text = ", ".join(labels)
                
                lines.append(f"{friendly}: {binding_text}")
            
            # Calculate visible area
            max_visible_lines = (height - 4) // (char_height + line_spacing)
            
            # Position in top-left
            x_pos = 2
            y_pos_start = 2
            
            # Render visible lines (just show what fits, starting from the top)
            visible_lines = lines[:max_visible_lines]
            for i, line in enumerate(visible_lines):
                y_pos = y_pos_start + i * (char_height + line_spacing)
                if y_pos + char_height > height:
                    break
                overlay_renderer.draw_text(line, x_pos, y_pos, color=(255, 255, 255), scale=1)
            
            # Show indicator if there are more items than can be displayed
            if len(lines) > max_visible_lines:
                remaining = len(lines) - max_visible_lines
                indicator_text = f"... {remaining} more"
                y_bottom = y_pos_start + max_visible_lines * (char_height + line_spacing)
                if y_bottom < height:
                    overlay_renderer.draw_text(indicator_text, x_pos, y_bottom, color=(150, 150, 150), scale=1)
        except Exception:
            pass
        
        return result
    
    def render_preview(
        self,
        width: int,
        height: int,
        preview_source: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Render visualization preview.
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            preview_source: Optional preview framebuffer to display
        
        Returns:
            Numpy array (H, W, 3) with preview rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        
        if preview_source is None:
            return result
        
        if width == 0 or height == 0:
            return result
        
        # Calculate preview size to fit in available space
        preview_height, preview_width = preview_source.shape[:2]
        
        # Scale to fit (with small margin)
        margin = 4
        max_width = width - margin * 2
        max_height = height - margin * 2
        
        scale_w = max_width / preview_width
        scale_h = max_height / preview_height
        scale = min(scale_w, scale_h, 1.0)  # Don't scale up, only down
        
        scaled_width = int(preview_width * scale)
        scaled_height = int(preview_height * scale)
        
        # Center in available space
        x_pos = (width - scaled_width) // 2
        y_pos = (height - scaled_height) // 2
        
        # Scale the preview source
        if scale < 1.0:
            # Use numpy linspace for nearest-neighbor resize
            y_indices = np.linspace(0, preview_height - 1, scaled_height).astype(int)
            x_indices = np.linspace(0, preview_width - 1, scaled_width).astype(int)
            scaled_preview = preview_source[np.ix_(y_indices, x_indices)]
        else:
            # No scaling needed, just crop to size
            scaled_preview = preview_source[:scaled_height, :scaled_width, :]
        
        # Copy scaled preview into result
        if x_pos + scaled_width <= width and y_pos + scaled_height <= height:
            result[y_pos:y_pos + scaled_height, x_pos:x_pos + scaled_width] = scaled_preview
        
        return result
    
    def render_debug_info(
        self,
        width: int,
        height: int,
        fps: float,
        renderer: Optional[Any] = None,
        viz_window: Optional[Any] = None,
    ) -> np.ndarray:
        """
        Render debug information (FPS, camera, mouse, parameters, resolutions).
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            fps: Current FPS value
            renderer: Optional renderer instance to get camera/mouse/params
            viz_window: Optional visualization window to get resolution info
        
        Returns:
            Numpy array (H, W, 3) with debug info rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        debug_renderer = MenuRenderer(result)
        char_width = 6
        char_height = 12
        line_spacing = 3
        
        lines: List[str] = []
        
        # Line 1: FPS
        fps_text = f'FPS: {fps:.1f}'
        lines.append(fps_text)
        
        # Resolution information from visualization window
        if viz_window:
            try:
                render_res = viz_window.get_render_resolution()
                window_size = viz_window.get_window_size()
                fb_size = viz_window.get_framebuffer_size()
                
                lines.append(f'Shader Render: {render_res[0]}×{render_res[1]}')
                lines.append(f'Window Size: {window_size[0]}×{window_size[1]}')
                if fb_size != window_size:
                    lines.append(f'Framebuffer: {fb_size[0]}×{fb_size[1]}')
            except Exception:
                pass
        
        # Camera information (if renderer available)
        if renderer:
            try:
                camera_source = renderer.get_camera_source()
                if camera_source:
                    camera_uniforms = camera_source.get_uniforms()
                    cam_pos = camera_uniforms.get('iCameraPos', (0.0, 0.0, 0.0))
                    cam_right = camera_uniforms.get('iCameraRight', (0.0, 0.0, 0.0))
                    cam_up = camera_uniforms.get('iCameraUp', (0.0, 0.0, 0.0))
                    cam_forward = camera_uniforms.get('iCameraForward', (0.0, 0.0, 0.0))
                    
                    lines.append(f'Cam Pos: ({cam_pos[0]:.2f},{cam_pos[1]:.2f},{cam_pos[2]:.2f})')
                    lines.append(f'Cam Fwd: ({cam_forward[0]:.2f},{cam_forward[1]:.2f},{cam_forward[2]:.2f})')
                    lines.append(f'Cam Up: ({cam_up[0]:.2f},{cam_up[1]:.2f},{cam_up[2]:.2f})')
                    lines.append(f'Cam Rgt: ({cam_right[0]:.2f},{cam_right[1]:.2f},{cam_right[2]:.2f})')
                    
                    # Show spherical camera parameters if available
                    camera = camera_source.get_camera()
                    from cube.shader.camera_modes import SphericalCamera
                    if isinstance(camera, SphericalCamera):
                        lines.append(f'Dist: {camera.distance:.2f} Yaw: {camera.yaw:.2f} Pitch: {camera.pitch:.2f}')
                        if abs(camera.roll) > 0.001:
                            lines.append(f'Roll: {camera.roll:.2f}')
            except Exception:
                pass
        
        # Line 3: Mouse position (if renderer available)
        if renderer:
            try:
                mouse_source = renderer.get_mouse_source()
                if mouse_source:
                    mouse_uniforms = mouse_source.get_uniforms()
                    mouse = mouse_uniforms.get('iMouse', (0.0, 0.0, 0.0, 0.0))
                    mouse_text = f'Mouse: ({mouse[0]:.0f},{mouse[1]:.0f})'
                    if mouse[2] > 0.0 or mouse[3] > 0.0:
                        mouse_text += f' click:({mouse[2]:.0f},{mouse[3]:.0f})'
                    lines.append(mouse_text)
            except Exception:
                pass
        
        # Parameters iParam0-7 from renderer state
        params = None
        if renderer:
            try:
                debug_state = renderer.get_debug_state()
                params = debug_state.get('params')
            except Exception:
                params = None
        
        param_line_start = None
        if params is not None:
            param_line_start = len(lines)
            first_row = ' '.join(f'{p:.2f}' for p in params[:4])
            second_row = ' '.join(f'{p:.2f}' for p in params[4:])
            lines.append(first_row)
            lines.append(second_row)
        
        # Layout text at bottom-right
        max_text_len = max((len(line) for line in lines)) if lines else 0
        text_width = max_text_len * char_width
        
        # Position at bottom-right
        x_pos = width - text_width - 2
        y_start_pos = height - len(lines) * (char_height + line_spacing) - 2
        
        for i, line in enumerate(lines):
            y_pos = y_start_pos + i * (char_height + line_spacing)
            if y_pos < 0:
                break
            if i == 0:
                color = (0, 255, 0)  # Green for FPS
            elif line.startswith('Cam ') or line.startswith('Dist:') or line.startswith('Roll:'):
                color = (100, 200, 255)  # Light blue for camera
            elif line.startswith('Mouse:'):
                color = (255, 150, 100)  # Orange for mouse
            elif param_line_start is not None and i >= param_line_start:
                color = (255, 255, 0)  # Yellow for params
            else:
                color = (200, 200, 200)  # Gray for other
            debug_renderer.draw_text(line, x_pos, y_pos, color=color, scale=1)
        
        return result
    
    def _init_pygame_font(self, size: int = 11):
        """Lazily initialize pygame font if available."""
        try:
            import pygame
            pygame.font.init()
            # Always create font with requested size (don't cache, size may vary)
            font = pygame.font.Font(None, size)
            self._pygame_available = True
            return font
        except (ImportError, Exception):
            self._pygame_available = False
            return None
    
    def handle_mouse_scroll(self, scroll_delta: int):
        """
        Handle mouse scroll event for effects list.
        
        Args:
            scroll_delta: Scroll amount (positive = scroll down, negative = scroll up)
        """
        self._effects_scroll_offset_pygame = max(0, self._effects_scroll_offset_pygame - scroll_delta)
    
    def render_effects_list_pygame(
        self,
        width: int,
        height: int,
        renderer: Optional[Any] = None,
        input_manager: Optional[Any] = None,
    ) -> np.ndarray:
        """
        Render active effects list using pygame fonts with mouse scrolling.
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            renderer: Optional renderer instance to get effect manager
            input_manager: Optional input manager for bindings
        
        Returns:
            Numpy array (H, W, 3) with effects list rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Render at 4x resolution for better quality, then scale down
        render_scale = 4
        render_width = width * render_scale
        render_height = height * render_scale
        
        pygame_font = self._init_pygame_font(size=12 * render_scale)
        if pygame_font is None:
            return result
        
        if not renderer or not hasattr(renderer, "effect_manager"):
            return result
        
        try:
            import pygame
            
            effect_manager = renderer.effect_manager
            active_actions = effect_manager.get_active_actions()
            
            if not active_actions:
                return result
            
            lines: List[Tuple[str, Tuple[int, int, int]]] = []
            for action in active_actions:
                friendly = action.name.replace("TOGGLE_", "").replace("_", " ").title()
                binding_text = "[unbound]"
                
                if input_manager and hasattr(input_manager, 'bindings'):
                    from cube.input.actions import InputContext
                    raw_bindings = input_manager.bindings.get_raw_inputs(
                        action, InputContext.VISUALIZATION
                    )
                    if raw_bindings:
                        labels = [self._format_binding_label(b) for b in raw_bindings]
                        binding_text = ", ".join(labels)
                
                line_text = f"{friendly}: {binding_text}"
                lines.append((line_text, (255, 255, 255)))
            
            if not lines:
                return result
            
            padding = 4 * render_scale
            line_height = 18 * render_scale
            
            # Calculate how many lines can actually fit
            # First, render a sample line to get actual text height
            sample_text = pygame_font.render("Sample", False, (255, 255, 255))
            actual_line_height = sample_text.get_height() + 1  # text height + spacing
            
            # Calculate max visible lines based on actual text height
            available_height = render_height - padding * 2
            max_visible_lines = available_height // actual_line_height if actual_line_height > 0 else len(lines)
            
            # Only scroll if we have more lines than can fit
            if len(lines) <= max_visible_lines:
                # All lines fit - show all, no scrolling
                self._effects_scroll_offset_pygame = 0
                visible_start = 0
                visible_end = len(lines)
                max_scroll_offset = 0
            else:
                # More lines than fit - enable scrolling
                max_scroll_offset = len(lines) - max_visible_lines
                self._effects_scroll_offset_pygame = min(self._effects_scroll_offset_pygame, max_scroll_offset)
                visible_start = self._effects_scroll_offset_pygame
                visible_end = min(visible_start + max_visible_lines, len(lines))
            
            pygame_surface = pygame.Surface((render_width, render_height))
            pygame_surface.fill((0, 0, 0))
            
            # Draw subtle border
            border_color = (100, 100, 100)
            pygame.draw.rect(pygame_surface, border_color, (0, 0, render_width, render_height), 1)
            
            y_pos = padding
            for i in range(visible_start, visible_end):
                line_text, color = lines[i]
                text_surface = pygame_font.render(line_text, False, color)
                text_height = text_surface.get_height()
                pygame_surface.blit(text_surface, (padding, y_pos))
                y_pos += text_height + 1
                # Stop if we've run out of vertical space
                if y_pos + text_height > render_height - padding:
                    break
            
            if max_scroll_offset > 0:
                if self._effects_scroll_offset_pygame > 0:
                    indicator = pygame_font.render(
                        f"↑ {self._effects_scroll_offset_pygame} above", 
                        False, (150, 150, 150)
                    )
                    pygame_surface.blit(indicator, (padding, padding))
                
                remaining = max_scroll_offset - self._effects_scroll_offset_pygame
                if remaining > 0:
                    indicator = pygame_font.render(
                        f"↓ {remaining} below", 
                        False, (150, 150, 150)
                    )
                    pygame_surface.blit(indicator, (padding, render_height - line_height - padding))
            
            # Scale down from high-res to target resolution using nearest-neighbor
            pygame_array = pygame.surfarray.array3d(pygame_surface)
            high_res = np.transpose(pygame_array, (1, 0, 2))
            
            # Downscale using nearest-neighbor
            y_indices = np.linspace(0, render_height - 1, height).astype(int)
            x_indices = np.linspace(0, render_width - 1, width).astype(int)
            result = high_res[np.ix_(y_indices, x_indices)]
            
        except Exception:
            pass
        
        return result
    
    def _format_binding_label(self, raw_input: tuple[str]) -> str:
        """Format a raw binding tuple for display."""
        parts = []
        for key in raw_input:
            if key.startswith("key:"):
                parts.append(key.split("key:", 1)[1])
            elif key.startswith("midi:"):
                parts.append(key.split("midi:", 1)[1])
            else:
                parts.append(key)
        return "+".join(parts)

