"""
Refactored LED Cube Controller with clean menu navigation and visualization management.

This demonstrates a cleaner architecture that:
- Separates menu navigation from visualization configuration
- Uses structured actions instead of string parsing
- Eliminates special cases and legacy redirects
"""

import time
from pathlib import Path
from typing import Optional
import tempfile

from cube.display import Display
from cube.input import InputHandler
from cube.menu.menu_renderer import MenuRenderer
from cube.menu.navigation import MenuNavigator
from cube.menu.actions import (
    MenuAction, QuitAction, LaunchVisualizationAction, MixerAction
)
from cube.menu.menu_states_v2 import (
    MainMenu, VisualizationModeSelect, ShaderBrowser, SettingsMenu
)
from cube.render import UnifiedRenderer, SurfacePixelMapper, CubePixelMapper
from cube.shader import SphericalCamera
from cube.shader.template_engine import ShaderTemplateEngine


class CubeControllerV2:
    """
    Main controller with clean separation of concerns.

    The controller handles:
    - Menu navigation (delegated to MenuNavigator)
    - Visualization launching based on structured actions
    - Main run loop
    """

    def __init__(self, width: int, height: int, num_panels: int = 6, fps: int = 30,
                 default_brightness: float = 90.0, default_gamma: float = 1.0,
                 scale: int = 1, **kwargs):
        """Initialize the controller."""
        
        self.window_width = width
        self.window_height = height
        self.fps = fps
        self.frame_time = 1.0 / fps
        self.num_panels = num_panels
        self.default_brightness = default_brightness
        self.default_gamma = default_gamma

        # Create display with 3 layers
        # Layer 0: Menu
        # Layer 1: Shader
        # Layer 2: Debug overlay (always on top)
        self.display = Display(width, height, num_layers=3, scale=scale,**kwargs)

        # Use display's actual render resolution (may be scaled down)
        self.width = self.display.width
        self.height = self.display.height

        # Calculate panel dimensions (can be rectangular for non-square displays)
        if self.num_panels == 1:
            self.panel_width = self.width
            self.panel_height = self.height
        else:
            # Horizontal layout: divide width, use full height
            self.panel_width = self.width // self.num_panels
            self.panel_height = self.height

        # Get layer references
        self.menu_layer = self.display.get_layer(0)      # Menu rendering
        self.shader_layer = self.display.get_layer(1)    # Shader output
        self.debug_layer = self.display.get_layer(2)     # Debug overlay (FPS, etc.)

        # Settings
        self.settings = {
            'debug_ui': False,
            'debug_axes': False,
            'brightness': default_brightness,
            'gamma': default_gamma,
            'fps_limit': fps,
        }

        self.input_handler = InputHandler()

        # Create menu renderer (renders directly to menu layer)
        self.menu_renderer = MenuRenderer(self.menu_layer)

        # Initialize menu navigation (use display's actual dimensions)
        self.menu_navigator = MenuNavigator(self.width, self.height, self.settings)
        self._register_menus()

        # Visualization state
        self.unified_renderer: Optional[UnifiedRenderer] = None
        self.current_shader_path: Optional[Path] = None
        self.is_visualizing = False

    def _register_menus(self):
        """Register all menu states with the navigator."""
        self.menu_navigator.register_menu('main', MainMenu())
        self.menu_navigator.register_menu('visualization_mode', VisualizationModeSelect())
        self.menu_navigator.register_menu('surface_browser', ShaderBrowser('surface'))
        self.menu_navigator.register_menu('cube_browser', ShaderBrowser('cube'))
        self.menu_navigator.register_menu('settings', SettingsMenu())

        # Start at main menu
        self.menu_navigator.navigate_to('main')

    def run(self):
        """Main run loop."""
        print("\nStarting cube controller...")
        print("Controls: Arrow keys to navigate, Enter to select, ESC to back/exit")

        clock = time.time()
        running = True

        while running:
            frame_start = time.time()

            # Handle input - get events from display and update input handler
            events = self.display.handle_events()
            self.input_handler.update(events)

            # Check for quit
            if self.input_handler.is_quit_requested():
                running = False
                break

            # Get the key that was pressed this frame
            key = self.input_handler.get_pressed_key()

            if self.is_visualizing:
                # Handle visualization input
                if self.input_handler.is_exit_requested():
                    self._stop_visualization()
                elif self.input_handler.is_key_pressed('r', 'reload') and self.current_shader_path:
                    self._reload_shader()
            else:
                # Handle menu input
                if key:
                    action = self.menu_navigator.handle_input(key)
                    if action:
                        running = self._handle_action(action)

            # Render
            if self.is_visualizing:
                self._render_visualization()
            else:
                self._render_menu()

            # Frame rate limiting
            frame_time = time.time() - frame_start
            sleep_time = (1.0 / self.fps) - frame_time
            if sleep_time > 0:
                time.sleep(sleep_time)

        print("Shutdown complete")

    def _handle_action(self, action: MenuAction) -> bool:
        """
        Handle an action from the menu system.

        Returns:
            True to continue running, False to quit.
        """
        if isinstance(action, QuitAction):
            return False

        elif isinstance(action, LaunchVisualizationAction):
            self._launch_visualization(action)
            return True

        elif isinstance(action, MixerAction):
            # TODO: Handle mixer actions
            print(f"Mixer action not yet implemented: {action}")
            return True

        return True

    def _launch_visualization(self, action: LaunchVisualizationAction):
        """Launch a visualization based on the action configuration."""
        print(f"\n{'='*60}")
        print(f"Launching visualization")
        print(f"Pixel mapper: {action.pixel_mapper}")

        # Generate or load shader
        if action.primitive:
            # Generate shader from primitive template
            print(f"Generating shader for primitive: {action.primitive}")
            engine = ShaderTemplateEngine()
            shader_code = engine.generate(action.primitive)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.glsl', delete=False) as f:
                f.write(shader_code)
                shader_path = Path(f.name)
        else:
            shader_path = action.shader_path

        print(f"Shader: {shader_path}")
        print(f"{'='*60}")
        print("Controls:")
        print("  Arrow keys: Rotate view")
        print("  Shift+arrows: Zoom")
        print("  R: Reload shader")
        print("  ESC: Return to menu")

        try:
            # Create pixel mapper
            if action.pixel_mapper == 'surface':
                camera = SphericalCamera()
                pixel_mapper = SurfacePixelMapper(self.width, self.height, camera)
            elif action.pixel_mapper == 'cube':
                print(f"Cube panel dimensions: {self.panel_width}×{self.panel_height}")
                print(f"Cube num panels: {self.num_panels}")
                pixel_mapper = CubePixelMapper(
                    face_width=self.panel_width,
                    face_height=self.panel_height,
                    num_panels=self.num_panels
                )
            else:
                raise ValueError(f"Unknown pixel mapper: {action.pixel_mapper}")

            # Create renderer
            if self.unified_renderer:
                self.unified_renderer.cleanup()
            self.unified_renderer = UnifiedRenderer(pixel_mapper, self.settings)
            self.unified_renderer.load_shader(str(shader_path))

            self.current_shader_path = shader_path
            self.is_visualizing = True

            print("Visualization started. Press ESC to return to menu.")

        except Exception as e:
            print(f"Error launching visualization: {e}")
            import traceback
            traceback.print_exc()
            self.is_visualizing = False

    def _stop_visualization(self):
        """Stop current visualization and return to menu."""
        print("Returning to menu...")
        if self.unified_renderer:
            self.unified_renderer.cleanup()
            self.unified_renderer = None
        self.is_visualizing = False
        self.current_shader_path = None

    def _reload_shader(self):
        """Reload current shader."""
        if self.unified_renderer and self.current_shader_path:
            print(f"Reloading shader: {self.current_shader_path}")
            try:
                self.unified_renderer.load_shader(str(self.current_shader_path))
            except Exception as e:
                print(f"Error reloading shader: {e}")

    def _render_menu(self):
        """Render current menu."""
        # Clear shader layer when in menu mode
        self.shader_layer[:, :, :] = 0

        # Clear menu layer first to ensure clean render
        self.menu_layer[:, :, :] = 0

        # Render menu to menu layer
        self.menu_navigator.render(self.menu_renderer)

        # Show the composed layers
        self.display.show(
            brightness=self.settings.get('brightness', 90.0),
            gamma=self.settings.get('gamma', 1.0)
        )

    def _render_visualization(self):
        """Render current visualization."""
        if self.unified_renderer:
            # Apply input to shader keyboard controls and get states
            states = self.input_handler.apply_to_shader_keyboard(
                self.unified_renderer.keyboard_input
            )
            self.unified_renderer.shift_pressed = states['shift']

            # Update camera with keyboard input
            if hasattr(self.unified_renderer.pixel_mapper, 'update_cameras'):
                self.unified_renderer.pixel_mapper.update_cameras(
                    self.unified_renderer.keyboard_input,
                    states['shift']
                )

            # Clear menu layer during visualization
            self.menu_layer[:, :, :] = 0

            # Render shader output to shader layer
            framebuffer = self.unified_renderer.render()

            # Copy framebuffer to shader layer, handling size mismatch
            fb_height, fb_width = framebuffer.shape[:2]
            layer_height, layer_width = self.shader_layer.shape[:2]

            if fb_height == layer_height and fb_width == layer_width:
                # Direct copy if sizes match
                self.shader_layer[:] = framebuffer
            else:
                # Clear shader layer first
                self.shader_layer[:, :, :] = 0

                # Center the framebuffer in the shader layer
                y_offset = (layer_height - fb_height) // 2
                x_offset = (layer_width - fb_width) // 2

                # Copy framebuffer to centered position
                self.shader_layer[y_offset:y_offset+fb_height, x_offset:x_offset+fb_width] = framebuffer

            # Show the composed layers with brightness and gamma
            self.display.show(
                brightness=self.settings.get('brightness', 90.0),
                gamma=self.settings.get('gamma', 1.0)
            )


# Example usage
if __name__ == "__main__":
    controller = CubeControllerV2(
        width=256,
        height=128,
        num_panels=4,
        fps=30
    )
    controller.run()