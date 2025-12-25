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
        self._effects_scroll_offset = 0
    
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
            char_height = 8
            char_width = 4
            line_spacing = 2
            
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
            
            # Auto-scroll: if we have more lines than visible, show the most recent
            if len(lines) > max_visible_lines:
                self._effects_scroll_offset = len(lines) - max_visible_lines
            else:
                self._effects_scroll_offset = 0
            
            # Position in top-left
            x_pos = 2
            y_pos_start = 2
            
            # Render visible lines
            visible_lines = lines[self._effects_scroll_offset:]
            for i, line in enumerate(visible_lines):
                y_pos = y_pos_start + i * (char_height + line_spacing)
                if y_pos + char_height > height:
                    break
                overlay_renderer.draw_text(line, x_pos, y_pos, color=(255, 255, 255), scale=1)
            
            # Show scroll indicator if needed
            if self._effects_scroll_offset > 0:
                indicator_text = f"... ({self._effects_scroll_offset} more)"
                overlay_renderer.draw_text(indicator_text, x_pos, y_pos_start, color=(150, 150, 150), scale=1)
        except Exception:
            pass
        
        return result
    
    def render_waveforms(
        self,
        width: int,
        height: int,
        beat_phase: float = 0.0,
        beat_pulse: float = 0.0,
    ) -> np.ndarray:
        """
        Render beat waveforms.
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            beat_phase: Beat phase value (0.0-1.0)
            beat_pulse: Beat pulse value (0.0-1.0)
        
        Returns:
            Numpy array (H, W, 3) with waveforms rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        
        if width == 0 or height == 0:
            return result
        
        # Append new sample and clamp history
        self._beat_history.append((beat_phase, beat_pulse))
        max_samples = min(width - 4, 128)
        if len(self._beat_history) > max_samples:
            self._beat_history = self._beat_history[-max_samples:]
        
        wave_width = len(self._beat_history)
        if wave_width <= 1:
            return result
        
        # Waveform area: fill available space
        wave_height = height - 4
        wave_x_start = 2
        wave_y_start = height - wave_height - 2
        
        # Clear waveform area
        result[wave_y_start:height, wave_x_start:wave_x_start + wave_width, :] = 0
        
        # Draw waveforms
        phase_height = wave_height // 2
        pulse_height = wave_height // 2
        y_phase_top = wave_y_start
        y_phase_bottom = wave_y_start + phase_height - 1
        y_pulse_top = wave_y_start + phase_height
        y_pulse_bottom = wave_y_start + wave_height - 1
        
        for x_idx, (phase, pulse) in enumerate(self._beat_history):
            x = wave_x_start + x_idx
            if x >= width:
                break
            
            # Clamp values
            clamped_phase = max(0.0, min(1.0, phase))
            clamped_pulse = max(0.0, min(1.0, pulse))
            
            # Phase column (green)
            phase_fill = int(clamped_phase * (phase_height - 1))
            phase_bottom = y_phase_bottom - phase_fill
            
            result[phase_bottom:y_phase_bottom + 1, x, 0] = 0
            result[phase_bottom:y_phase_bottom + 1, x, 1] = 255
            result[phase_bottom:y_phase_bottom + 1, x, 2] = 0
            
            # Pulse column (pink)
            pulse_fill = int(clamped_pulse * (pulse_height - 1))
            pulse_bottom = y_pulse_bottom - pulse_fill
            
            result[pulse_bottom:y_pulse_bottom + 1, x, 0] = 255
            result[pulse_bottom:y_pulse_bottom + 1, x, 1] = 105
            result[pulse_bottom:y_pulse_bottom + 1, x, 2] = 180
        
        # Labels at left edge
        label_color_phase = (0, 255, 0)
        label_color_pulse = (255, 105, 180)
        
        if wave_width > 10:
            label_renderer = MenuRenderer(result)
            label_renderer.draw_text(
                "phase", wave_x_start + 2, wave_y_start, color=label_color_phase, scale=1)
            label_renderer.draw_text(
                "pulse", wave_x_start + 2, wave_y_start + phase_height, color=label_color_pulse, scale=1)
        
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
    ) -> np.ndarray:
        """
        Render debug information (FPS, camera, mouse, parameters).
        
        Args:
            width: Desired width in pixels
            height: Desired height in pixels
            fps: Current FPS value
            renderer: Optional renderer instance to get camera/mouse/params
        
        Returns:
            Numpy array (H, W, 3) with debug info rendered
        """
        result = np.zeros((height, width, 3), dtype=np.uint8)
        debug_renderer = MenuRenderer(result)
        char_width = 4
        char_height = 8
        line_spacing = 2
        
        lines: List[str] = []
        
        # Line 1: FPS
        fps_text = f'FPS: {fps:.1f}'
        lines.append(fps_text)
        
        # Line 2: Camera position (if renderer available)
        if renderer:
            try:
                camera_source = renderer.get_camera_source()
                if camera_source:
                    camera_uniforms = camera_source.get_uniforms()
                    cam_pos = camera_uniforms.get('iCameraPos', (0.0, 0.0, 0.0))
                    cam_text = f'Cam: ({cam_pos[0]:.1f},{cam_pos[1]:.1f},{cam_pos[2]:.1f})'
                    lines.append(cam_text)
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
            elif line.startswith('Cam:'):
                color = (100, 200, 255)  # Light blue for camera
            elif line.startswith('Mouse:'):
                color = (255, 150, 100)  # Orange for mouse
            elif param_line_start is not None and i >= param_line_start:
                color = (255, 255, 0)  # Yellow for params
            else:
                color = (200, 200, 200)  # Gray for other
            debug_renderer.draw_text(line, x_pos, y_pos, color=color, scale=1)
        
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

