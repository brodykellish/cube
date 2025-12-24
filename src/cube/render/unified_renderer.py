"""
Unified shader renderer with pluggable pixel mapping.

Combines GPU shader rendering with flexible pixel mapping strategies.
All rendering logic (shaders, uniforms, input) is shared. Only the
pixel mapping (how renders map to output) varies.
"""
import numpy as np
from OpenGL.GL import glViewport, glUniform3f, glUniform1f, glUseProgram
from cube.shader import ShaderRenderer, UniformSource
from cube.shader.camera_uniform_source import CameraUniformSource
from .pixel_mappers import PixelMapper


class UnifiedRenderer:
    """
    Unified shader renderer with pluggable pixel mapping.

    Separates shader execution (GPU, uniforms, input) from pixel layout.
    """

    def __init__(self, pixel_mapper: PixelMapper, settings: dict | None = None, uniform_sources: list | None = None):
        """
        Initialize unified renderer.

        Args:
            pixel_mapper: Strategy for mapping renders to output
            settings: Optional settings dictionary for debug flags, etc.
            uniform_sources: Optional list of additional uniform sources (MIDI, audio, etc.)
        """
        self.pixel_mapper = pixel_mapper
        self.settings = settings or {}

        specs = pixel_mapper.get_render_specs()
        max_width = max(spec.width for spec in specs)
        max_height = max(spec.height for spec in specs)

        self.gpu_renderer = ShaderRenderer(max_width, max_height)
        self.current_width = max_width
        self.current_height = max_height

        mapper_camera = getattr(pixel_mapper, 'camera', None)
        self.camera_source = CameraUniformSource(camera=mapper_camera)
        self.gpu_renderer.add_uniform_source(self.camera_source)

        if uniform_sources:
            for source in uniform_sources:
                # Avoid double-adding the camera source
                if not isinstance(source, CameraUniformSource):
                    self.gpu_renderer.add_uniform_source(source)

    def get_camera_source(self) -> CameraUniformSource:
        """Get the camera uniform source."""
        return self.camera_source

    def make_context_current(self) -> bool:
        """
        Make this renderer's OpenGL context current for the calling thread.

        This is required when using the renderer from a different thread than
        where it was created (e.g., background shader validation).

        Returns:
            True if context was made current, False otherwise
        """
        return self.gpu_renderer.make_context_current()

    def load_shader(self, shader_path: str) -> None:
        """Load shader file."""
        self.gpu_renderer.load_shader(shader_path)

    def add_input_source(self, source: UniformSource) -> None:
        """Add input source (audio, MIDI, etc.)."""
        self.gpu_renderer.add_uniform_source(source)

    def remove_input_source(self, source: UniformSource) -> None:
        """Remove input source."""
        self.gpu_renderer.remove_uniform_source(source)
    
    def update_mouse(self, x: float, y: float, button_pressed: bool = False):
        """
        Update mouse state for shader uniforms.
        
        Args:
            x: Mouse x position in pixels
            y: Mouse y position in pixels
            button_pressed: True if mouse button is pressed
        """
        if hasattr(self.gpu_renderer, 'update_mouse'):
            self.gpu_renderer.update_mouse(x, y, button_pressed)

    def render(self) -> np.ndarray:
        """
        Render using current pixel mapping strategy.

        Returns:
            Final framebuffer ready for display.
        """
        render_specs = self.pixel_mapper.get_render_specs()
        renders: list[np.ndarray] = []

        for i, spec in enumerate(render_specs):
            # Per-face camera repositioning for cube mapping
            if len(render_specs) > 1 and hasattr(self.pixel_mapper, 'reposition_camera_for_face'):
                self.pixel_mapper.reposition_camera_for_face(i, self.camera_source)

            # Resize viewport if needed
            if spec.width != self.current_width or spec.height != self.current_height:
                self._resize_viewport(spec.width, spec.height)

            # Optional debug axes uniform
            if getattr(self.gpu_renderer, 'program', None):
                glUseProgram(self.gpu_renderer.program)
                if hasattr(self.gpu_renderer, 'uniform_locs') and 'iDebugAxes' in self.gpu_renderer.uniform_locs:
                    debug_value = 1.0 if self.settings.get('debug_axes', False) else 0.0
                    glUniform1f(self.gpu_renderer.uniform_locs['iDebugAxes'], debug_value)

            self.gpu_renderer.render()
            pixels = self.gpu_renderer.read_pixels()
            renders.append(pixels)

        # Clear any temporary camera overrides
        if len(render_specs) > 1:
            self.camera_source.set_override_vectors(None)

        return self.pixel_mapper.layout_renders(renders)

    def _resize_viewport(self, width: int, height: int) -> None:
        """Resize GPU renderer viewport and update resolution uniforms."""
        self.gpu_renderer.width = width
        self.gpu_renderer.height = height
        self.current_width = width
        self.current_height = height

        glViewport(0, 0, width, height)

        # Keep iResolution in sync if the shader uses it
        if hasattr(self.gpu_renderer, 'uniform_locs') and 'iResolution' in self.gpu_renderer.uniform_locs:
            glUniform3f(self.gpu_renderer.uniform_locs['iResolution'], float(width), float(height), 1.0)

    def cleanup(self) -> None:
        """Clean up GPU resources."""
        self.gpu_renderer.cleanup()


