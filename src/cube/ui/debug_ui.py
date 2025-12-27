"""
Debug UI system with clean API and minimal state sharing.

Provides a data class for debug UI state and a stateless renderer.
"""
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field
from cube.menu.menu_renderer import MenuRenderer


@dataclass
class DebugUIData:
    """
    Container for all data needed to render the debug UI.
    
    This eliminates state sharing by collecting all necessary data
    into a single object that can be passed to the renderer.
    """
    # FPS and performance
    fps: float = 0.0
    
    # Visualization preview
    preview_framebuffer: Optional[np.ndarray] = None
    
    # Window/resolution info
    render_resolution: Optional[Tuple[int, int]] = None
    window_size: Optional[Tuple[int, int]] = None
    framebuffer_size: Optional[Tuple[int, int]] = None
    
    # Camera data
    camera_pos: Optional[Tuple[float, float, float]] = None
    camera_forward: Optional[Tuple[float, float, float]] = None
    camera_up: Optional[Tuple[float, float, float]] = None
    camera_right: Optional[Tuple[float, float, float]] = None
    camera_distance: Optional[float] = None
    camera_yaw: Optional[float] = None
    camera_pitch: Optional[float] = None
    camera_roll: Optional[float] = None
    
    # Mouse data
    mouse_pos: Optional[Tuple[float, float]] = None
    mouse_click: Optional[Tuple[float, float]] = None
    
    # Parameters
    params: List[float] = field(default_factory=lambda: [0.0] * 8)
    
    # Effects list
    active_effects: List[Tuple[str, str]] = field(default_factory=list)  # (name, binding)
    
    # Scroll state (temporary, should be managed externally)
    effects_scroll_offset: int = 0
    
    # Visualization state
    visualization_running: bool = False



def collect_debug_data(
    visualization_runner: Optional[Any] = None,
    viz_window: Optional[Any] = None,
    preview_framebuffer: Optional[np.ndarray] = None,
    viz_input_manager: Optional[Any] = None,
) -> DebugUIData:
    """
    Collect all debug UI data from various sources.
    
    This function centralizes data collection to avoid state sharing.
    
    Args:
        visualization_runner: Optional VisualizationRunner instance
        viz_window: Optional visualization window
        preview_framebuffer: Optional preview framebuffer
        viz_input_manager: Optional input manager for bindings
    
    Returns:
        DebugUIData object with all collected data
    """
    data = DebugUIData()
    
    # Check if visualization is actually running
    data.visualization_running = False
    if visualization_runner:
        try:
            # Check if thread is alive
            if hasattr(visualization_runner, '_thread') and visualization_runner._thread:
                data.visualization_running = visualization_runner._thread.is_alive()
            # Also check if window is focused/open
            if viz_window and hasattr(viz_window, 'is_focused'):
                data.visualization_running = data.visualization_running and viz_window.is_focused()
        except Exception:
            pass
    
    # FPS
    if visualization_runner and hasattr(visualization_runner, 'get_fps'):
        data.fps = visualization_runner.get_fps()
    
    # Preview framebuffer
    data.preview_framebuffer = preview_framebuffer
    
    # Window/resolution info
    if viz_window:
        try:
            data.render_resolution = viz_window.get_render_resolution()
            data.window_size = viz_window.get_window_size()
            data.framebuffer_size = viz_window.get_framebuffer_size()
        except Exception:
            pass
    
    # Camera data
    if visualization_runner:
        try:
            camera_source = None
            if hasattr(visualization_runner, 'get_camera_source'):
                camera_source = visualization_runner.get_camera_source()
            
            if camera_source:
                camera_uniforms = camera_source.get_uniforms()
                data.camera_pos = camera_uniforms.get('iCameraPos')
                data.camera_right = camera_uniforms.get('iCameraRight')
                data.camera_up = camera_uniforms.get('iCameraUp')
                data.camera_forward = camera_uniforms.get('iCameraForward')
                
                if hasattr(camera_source, 'get_camera'):
                    camera = camera_source.get_camera()
                    from cube.shader.camera_modes import SphericalCamera
                    if isinstance(camera, SphericalCamera):
                        data.camera_distance = camera.distance
                        data.camera_yaw = camera.yaw
                        data.camera_pitch = camera.pitch
                        data.camera_roll = camera.roll if abs(camera.roll) > 0.001 else None
        except Exception:
            pass
    
    # Mouse data
    if visualization_runner:
        try:
            mouse_source = None
            if hasattr(visualization_runner, 'get_mouse_source'):
                mouse_source = visualization_runner.get_mouse_source()
            
            if mouse_source:
                mouse_uniforms = mouse_source.get_uniforms()
                mouse = mouse_uniforms.get('iMouse', (0.0, 0.0, 0.0, 0.0))
                data.mouse_pos = (mouse[0], mouse[1])
                if mouse[2] > 0.0 or mouse[3] > 0.0:
                    data.mouse_click = (mouse[2], mouse[3])
        except Exception:
            pass
    
    # Parameters
    if visualization_runner:
        try:
            debug_state = visualization_runner.get_debug_state()
            params = debug_state.get('params', [0.0] * 8)
            # Ensure we have exactly 8 parameters
            if isinstance(params, list) and len(params) >= 8:
                data.params = params[:8]
            else:
                data.params = [0.0] * 8
        except Exception as e:
            # On error, ensure params are still set to default
            data.params = [0.0] * 8
            print(f"[DebugUI] Error getting parameters: {e}")
    
    # Active effects
    if visualization_runner:
        try:
            effect_manager = None
            if hasattr(visualization_runner, 'effect_manager'):
                effect_manager = visualization_runner.effect_manager
            elif hasattr(visualization_runner, '_effect_manager'):
                effect_manager = visualization_runner._effect_manager
            
            if effect_manager:
                active_actions = effect_manager.get_active_actions()
                
                for action in active_actions:
                    friendly = action.name.replace("TOGGLE_", "").replace("_", " ").title()
                    binding_text = "[unbound]"
                    
                    if viz_input_manager and hasattr(viz_input_manager, 'bindings'):
                        from cube.input.actions import InputContext
                        raw_bindings = viz_input_manager.bindings.get_raw_inputs(
                            action, InputContext.VISUALIZATION
                        )
                        if raw_bindings:
                            labels = [_format_binding_label(b) for b in raw_bindings]
                            binding_text = ", ".join(labels)
                    
                    data.active_effects.append((friendly, binding_text))
        except Exception:
            pass
    
    return data


def _format_binding_label(raw_input: tuple[str]) -> str:
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

class DebugUIRenderer:
    """
    Stateless debug UI renderer with clean API.
    
    Takes DebugUIData and renders it into numpy arrays.
    No internal state is maintained between calls.
    """
    
    def __init__(self):
        """Initialize renderer (no persistent state)."""
        pass
    
    def render_effects_list(
        self,
        width: int,
        height: int,
        data: DebugUIData,
    ) -> np.ndarray:
        """
        Render active effects list.
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            data: Debug UI data
        
        Returns:
            Numpy array (H, W, 3) with effects list rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        
        if not data.active_effects:
            return result
        
        try:
            overlay_renderer = MenuRenderer(result)
            char_height = 12
            char_width = 6
            line_spacing = 3
            
            lines: List[str] = []
            for effect_name, binding in data.active_effects:
                lines.append(f"{effect_name}: {binding}")
            
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
    
    def render_effects_list_pygame(
        self,
        width: int,
        height: int,
        data: DebugUIData,
    ) -> np.ndarray:
        """
        Render active effects list using pygame fonts with scrolling.
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            data: Debug UI data
        
        Returns:
            Numpy array (H, W, 3) with effects list rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        
        if not data.active_effects:
            return result
        
        try:
            import pygame
            pygame.font.init()
        except (ImportError, Exception):
            return result
        
        # Render at 4x resolution for better quality, then scale down
        render_scale = 4
        render_width = width * render_scale
        render_height = height * render_scale
        
        pygame_font = pygame.font.Font(None, 12 * render_scale)
        
        lines: List[Tuple[str, Tuple[int, int, int]]] = []
        for effect_name, binding in data.active_effects:
            line_text = f"{effect_name}: {binding}"
            lines.append((line_text, (255, 255, 255)))
        
        if not lines:
            return result
        
        padding = 4 * render_scale
        
        # Calculate how many lines can actually fit
        sample_text = pygame_font.render("Sample", False, (255, 255, 255))
        actual_line_height = sample_text.get_height() + 1
        
        available_height = render_height - padding * 2
        max_visible_lines = available_height // actual_line_height if actual_line_height > 0 else len(lines)
        
        # Handle scrolling (use local variable, don't modify data)
        scroll_offset = data.effects_scroll_offset
        if len(lines) <= max_visible_lines:
            scroll_offset = 0
            visible_start = 0
            visible_end = len(lines)
            max_scroll_offset = 0
        else:
            max_scroll_offset = len(lines) - max_visible_lines
            scroll_offset = min(scroll_offset, max_scroll_offset)
            visible_start = scroll_offset
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
            if y_pos + text_height > render_height - padding:
                break
        
        if max_scroll_offset > 0:
            if scroll_offset > 0:
                indicator = pygame_font.render(
                    f"↑ {scroll_offset} above", 
                    False, (150, 150, 150)
                )
                pygame_surface.blit(indicator, (padding, padding))
            
            remaining = max_scroll_offset - scroll_offset
            if remaining > 0:
                line_height = 18 * render_scale
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
        
        return result
    
    def render_preview(
        self,
        width: int,
        height: int,
        data: DebugUIData,
    ) -> np.ndarray:
        """
        Render visualization preview.
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            data: Debug UI data
        
        Returns:
            Numpy array (H, W, 3) with preview rendered (gray placeholder if no active visualization)
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Show gray placeholder if no preview framebuffer or visualization not running
        if data.preview_framebuffer is None or not data.visualization_running:
            # Fill with gray placeholder
            result[:, :] = (128, 128, 128)  # Gray
            return result
        
        preview_source = data.preview_framebuffer
        
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
        data: DebugUIData,
    ) -> np.ndarray:
        """
        Render debug information (FPS, camera, mouse, parameters, resolutions).
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            data: Debug UI data
        
        Returns:
            Numpy array (H, W, 3) with debug info rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        debug_renderer = MenuRenderer(result)
        char_width = 6
        char_height = 10
        line_spacing = 0
        
        # import pprint
        # pprint.pprint(f"Debug info data: {data}")
        lines: List[str] = []
        
        # FPS
        lines.append(f'FPS: {data.fps:.1f}')
        
        # Resolution information
        if data.render_resolution:
            lines.append(f'Shader Render: {data.render_resolution[0]}×{data.render_resolution[1]}')
        if data.window_size:
            lines.append(f'Window Size: {data.window_size[0]}×{data.window_size[1]}')
        if data.framebuffer_size and data.framebuffer_size != data.window_size:
            lines.append(f'Framebuffer: {data.framebuffer_size[0]}×{data.framebuffer_size[1]}')
        
        # Camera information
        if data.camera_pos:
            lines.append(f'Cam Pos: ({data.camera_pos[0]:.2f},{data.camera_pos[1]:.2f},{data.camera_pos[2]:.2f})')
            lines.append(f'Dist: {data.camera_distance if data.camera_distance else 0:.2f}, Yaw: {data.camera_yaw if data.camera_yaw else 0:.2f}')
            lines.append(f'Pitch: {data.camera_pitch if data.camera_pitch else 0:.2f}, Roll: {data.camera_roll if data.camera_roll else 0:.2f}')

        # Mouse position
        if data.mouse_pos:
            mouse_text = f'Mouse: ({data.mouse_pos[0]:.2f},{data.mouse_pos[1]:.2f})'
            if data.mouse_click:
                mouse_text += f' click:({data.mouse_click[0]:.2f},{data.mouse_click[1]:.2f})'
            lines.append(mouse_text)
    

        # Parameters (always show, even if all zeros)
        param_line_start = None
        if data.params and len(data.params) >= 8:
            param_line_start = len(lines)
            first_row = ' '.join(f'{p:.2f}' for p in data.params[:4])
            second_row = ' '.join(f'{p:.2f}' for p in data.params[4:])
            lines.append(first_row)
            lines.append(second_row)
        elif not data.params or len(data.params) < 8:
            # Show placeholder if params not available
            param_line_start = len(lines)
            lines.append('0.00 0.00 0.00 0.00')
            lines.append('0.00 0.00 0.00 0.00')
        
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

