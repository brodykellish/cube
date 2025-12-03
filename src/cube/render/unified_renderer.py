"""
Unified shader renderer with pluggable pixel mapping.

Combines GPU shader rendering with flexible pixel mapping strategies.
All rendering logic (shaders, uniforms, input) is shared. Only the
pixel mapping (how renders map to output) varies.
"""

import numpy as np
from OpenGL.GL import glViewport, glUniform3f, glUniform1f, glUseProgram

from cube.shader import ShaderRenderer, UniformSource
from .pixel_mappers import PixelMapper


class UnifiedRenderer:
    """
    Unified shader renderer with pluggable pixel mapping.

    Separates shader execution (GPU, uniforms, input) from pixel layout.
    """

    def __init__(self, pixel_mapper: PixelMapper, settings: dict = None):
        """
        Initialize unified renderer.

        Args:
            pixel_mapper: Strategy for mapping renders to output
            settings: Optional settings dictionary for debug flags, etc.
        """
        self.pixel_mapper = pixel_mapper
        self.settings = settings or {}

        # Determine max dimensions we'll need
        specs = pixel_mapper.get_render_specs()
        max_width = max(spec.width for spec in specs)
        max_height = max(spec.height for spec in specs)

        # Create GPU renderer
        self.gpu_renderer = ShaderRenderer(max_width, max_height)
        self.current_width = max_width
        self.current_height = max_height

        # Initialize cameras from pixel mapper
        self._init_cameras()

    @property
    def keyboard_input(self):
        """Access keyboard input handler."""
        return self.gpu_renderer.keyboard_input

    @property
    def shift_pressed(self):
        """Get shift key state."""
        return self.gpu_renderer.shift_pressed

    @shift_pressed.setter
    def shift_pressed(self, value: bool):
        """Set shift key state."""
        self.gpu_renderer.shift_pressed = value

    def load_shader(self, shader_path: str):
        """Load shader file."""
        self.gpu_renderer.load_shader(shader_path)

    def add_input_source(self, source: UniformSource):
        """Add input source (audio, MIDI, etc.)."""
        self.gpu_renderer.add_uniform_source(source)

    def remove_input_source(self, source: UniformSource):
        """Remove input source."""
        self.gpu_renderer.remove_uniform_source(source)

    def _init_cameras(self):
        """Initialize camera instances from pixel mapper specs."""
        specs = self.pixel_mapper.get_render_specs()
        self.cameras = [spec.camera for spec in specs]

        # Set initial camera (will be switched during multi-pass rendering)
        if self.cameras:
            self.gpu_renderer.set_camera_mode(self.cameras[0])

    def render(self) -> np.ndarray:
        """
        Render using current pixel mapping strategy.

        Returns:
            Final framebuffer ready for display
        """
        # Update volumetric cameras if pixel mapper supports it
        if hasattr(self.pixel_mapper, 'update_cameras'):
            self.pixel_mapper.update_cameras(
                self.gpu_renderer.keyboard_input,
                self.gpu_renderer.shift_pressed
            )

        render_specs = self.pixel_mapper.get_render_specs()
        renders = []

        for i, spec in enumerate(render_specs):
            # For multi-pass rendering, switch camera for each pass
            # For single-pass, keep the same camera instance (accumulates keyboard input)
            if len(render_specs) > 1:
                self.gpu_renderer.set_camera_mode(self.cameras[i])

            # Resize viewport if needed
            if spec.width != self.current_width or spec.height != self.current_height:
                self._resize_viewport(spec.width, spec.height)

            # Set debug uniforms if available
            if hasattr(self.gpu_renderer, 'program') and self.gpu_renderer.program:
                glUseProgram(self.gpu_renderer.program)
                if hasattr(self.gpu_renderer, 'uniform_locs') and 'iDebugAxes' in self.gpu_renderer.uniform_locs:
                    debug_value = 1.0 if self.settings.get('debug_axes', False) else 0.0
                    glUniform1f(self.gpu_renderer.uniform_locs['iDebugAxes'], debug_value)

            # Render this pass
            self.gpu_renderer.render()
            pixels = self.gpu_renderer.read_pixels()
            renders.append(pixels)

        # Layout all renders into final framebuffer
        return self.pixel_mapper.layout_renders(renders)

    def _resize_viewport(self, width: int, height: int):
        """Resize GPU renderer viewport."""
        self.gpu_renderer.width = width
        self.gpu_renderer.height = height
        self.current_width = width
        self.current_height = height

        glViewport(0, 0, width, height)

        # Update iResolution uniform
        if hasattr(self.gpu_renderer, 'uniform_locs') and 'iResolution' in self.gpu_renderer.uniform_locs:
            glUniform3f(
                self.gpu_renderer.uniform_locs['iResolution'],
                float(width), float(height), 1.0
            )

    def cleanup(self):
        """Clean up GPU resources."""
        self.gpu_renderer.cleanup()
