"""
Standalone debug renderer utility for both menu and visualization windows.

Provides reusable debug overlay rendering functionality.
"""
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from cube.menu.menu_renderer import MenuRenderer


class DebugRenderer:
    """
    Standalone debug renderer that can be used by both menu and visualization windows.
    
    Renders:
    - FPS counter
    - Camera position
    - Mouse position
    - Parameters (iParam0-7)
    - Beat waveform visualization
    - Active effects overlay
    """
    
    def __init__(self):
        """Initialize debug renderer."""
        self._beat_history: List[Tuple[float, float]] = []
    
    def render(
        self,
        debug_layer: np.ndarray,
        settings: Dict[str, Any],
        fps: float,
        renderer: Optional[Any] = None,
        beat_phase: float = 0.0,
        beat_pulse: float = 0.0,
        input_manager: Optional[Any] = None,
        context: str = 'menu',
    ) -> None:
        """
        Render debug overlay to debug layer.
        
        Args:
            debug_layer: Numpy array (H, W, 3) to render into
            settings: Settings dict with 'menu_debug_ui' or 'viz_debug_ui' key
            fps: Current FPS value
            renderer: Optional renderer instance to get camera/mouse/params/effects
            beat_phase: Beat phase value (0.0-1.0)
            beat_pulse: Beat pulse value (0.0-1.0)
            input_manager: Optional input manager for bindings
            context: Context string - 'menu' or 'viz' to determine which setting to check
        """
        # Clear debug layer
        debug_layer[:, :, :] = 0
        
        # Check if debug UI is enabled for this specific context
        if context == 'menu':
            debug_enabled = settings.get('menu_debug_ui', False)
        elif context == 'viz':
            debug_enabled = settings.get('viz_debug_ui', False)
        else:
            debug_enabled = False
        
        if not debug_enabled:
            return
        
        height, width = debug_layer.shape[:2]
        debug_renderer = MenuRenderer(debug_layer)
        
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
        
        # Line 4-5: Parameters iParam0-7 from renderer state
        params = None
        if renderer:
            try:
                debug_state = renderer.get_debug_state()
                params = debug_state.get('params')
                # Use provided beat_phase/pulse or get from debug_state
                if beat_phase == 0.0 and beat_pulse == 0.0:
                    beat_phase = float(debug_state.get('beat_phase', 0.0))
                    beat_pulse = float(debug_state.get('beat_pulse', 0.0))
            except Exception:
                params = None
        
        param_line_start = None
        if params is not None:
            param_line_start = len(lines)
            first_row = ' '.join(f'{p:.2f}' for p in params[:4])
            second_row = ' '.join(f'{p:.2f}' for p in params[4:])
            lines.append(first_row)
            lines.append(second_row)
        
        # Layout text in top-right corner
        max_text_len = max((len(line) for line in lines)) if lines else 0
        text_width = max_text_len * char_width
        x_pos = width - text_width - 2
        y_start = height - len(lines) * (char_height + line_spacing) - 2
        
        for i, line in enumerate(lines):
            y_pos = y_start + i * (char_height + line_spacing)
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
        
        # Render active effects overlay (top-left)
        self._render_effect_overlay(debug_layer, renderer, input_manager)
        
        # Render beat waveform (bottom-left)
        self._render_beat_waveform(debug_layer, beat_phase, beat_pulse)
    
    def _render_effect_overlay(
        self, 
        debug_layer: np.ndarray, 
        renderer: Optional[Any],
        input_manager: Optional[Any] = None
    ) -> None:
        """Render active effects and their deactivation bindings in top-left."""
        if not renderer or not hasattr(renderer, "effect_manager"):
            return
        
        try:
            effect_manager = renderer.effect_manager
            active_actions = effect_manager.get_active_actions()
            
            if not active_actions:
                return
            
            overlay_renderer = MenuRenderer(debug_layer)
            char_height = 8
            line_spacing = 2
            x_pos = 2
            y_start = 2
            
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
            
            for i, line in enumerate(lines):
                y_pos = y_start + i * (char_height + line_spacing)
                overlay_renderer.draw_text(line, x_pos, y_pos, color=(255, 255, 255), scale=1)
        except Exception:
            pass
    
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
    
    def _render_beat_waveform(
        self, 
        debug_layer: np.ndarray, 
        beat_phase: float, 
        beat_pulse: float
    ) -> None:
        """Render simple waveform visualization for beat phase/pulse in bottom-left."""
        height, width = debug_layer.shape[:2]
        if width == 0 or height == 0:
            return
        
        # Append new sample and clamp history
        self._beat_history.append((beat_phase, beat_pulse))
        max_samples = min(width // 2, 128)
        if len(self._beat_history) > max_samples:
            self._beat_history = self._beat_history[-max_samples:]
        
        wave_width = len(self._beat_history)
        if wave_width <= 1:
            return
        
        # Waveform area: bottom-left, fixed height
        wave_height = 40
        x_start = 2
        y_start = height - wave_height - 2
        
        # Clear waveform area
        debug_layer[y_start:height, x_start:x_start + wave_width, :] = 0
        
        # Draw waveforms
        phase_height = wave_height // 2
        pulse_height = wave_height // 2
        y_phase_top = y_start
        y_phase_bottom = y_start + phase_height - 1
        y_pulse_top = y_start + phase_height
        y_pulse_bottom = y_start + wave_height - 1
        
        for x_idx, (phase, pulse) in enumerate(self._beat_history):
            x = x_start + x_idx
            
            # Clamp values
            clamped_phase = max(0.0, min(1.0, phase))
            clamped_pulse = max(0.0, min(1.0, pulse))
            
            # Phase column (green)
            phase_fill = int(clamped_phase * (phase_height - 1))
            phase_bottom = y_phase_bottom - phase_fill
            
            debug_layer[phase_bottom:y_phase_bottom + 1, x, 0] = 0
            debug_layer[phase_bottom:y_phase_bottom + 1, x, 1] = 255
            debug_layer[phase_bottom:y_phase_bottom + 1, x, 2] = 0
            
            # Pulse column (pink)
            pulse_fill = int(clamped_pulse * (pulse_height - 1))
            pulse_bottom = y_pulse_bottom - pulse_fill
            
            debug_layer[pulse_bottom:y_pulse_bottom + 1, x, 0] = 255
            debug_layer[pulse_bottom:y_pulse_bottom + 1, x, 1] = 105
            debug_layer[pulse_bottom:y_pulse_bottom + 1, x, 2] = 180
        
        # Labels at left edge
        label_color_phase = (0, 255, 0)
        label_color_pulse = (255, 105, 180)
        
        if wave_width > 10:  # Only draw labels if there's space
            label_renderer = MenuRenderer(debug_layer)
            label_renderer.draw_text(
                "phase", x_start + 2, y_start, color=label_color_phase, scale=1)
            label_renderer.draw_text(
                "pulse", x_start + 2, y_start + phase_height, color=label_color_pulse, scale=1)

