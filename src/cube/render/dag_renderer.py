"""
DAG-based renderer for cube.

Replaces UnifiedRenderer with DAG-based rendering pipeline while maintaining
the same public API for compatibility.
"""

import numpy as np
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from OpenGL.GL import *

from cube.shader import ShaderRenderer, UniformSource
from cube.shader.camera_uniform_source import CameraUniformSource
from cube.shader.parameter_uniform_source import ParameterUniformSource
from cube.shader.shader_loader import load_shader_program
from cube.dag.dag import DAG
from cube.dag.effect_node import EffectNode
from cube.dag.source_node import SourceNode
from cube.render.effect_manager import EffectManager, TriggerMode
from cube.render.effect_config_loader import load_effect_config
from cube.input.actions import Action
from cube.utils.gl_utils import create_fullscreen_quad
from cube.utils.texture_utils import read_texture_to_numpy
from .pixel_mappers import PixelMapper, RenderSpec


class DAGRenderer:
    """
    DAG-based shader renderer with pluggable pixel mapping.
    
    Maintains the same public API as UnifiedRenderer for compatibility.
    Uses DAG-based rendering pipeline internally.
    """
    
    def __init__(self, pixel_mapper: PixelMapper, input_manager,
                 settings: dict = None, uniform_sources: list = None,
                 audio_mapping_source=None):
        """
        Initialize DAG renderer.
        
        Args:
            pixel_mapper: Strategy for mapping renders to output
            input_manager: InputManager for camera and parameter control
            settings: Optional settings dictionary for debug flags, etc.
            uniform_sources: Optional list of additional uniform sources (audio, etc.)
            audio_mapping_source: Optional AudioUniformMappingSource for audio→uniform mappings
        """
        self.pixel_mapper = pixel_mapper
        self.settings = settings or {}
        self.input_manager = input_manager
        
        # Determine max dimensions we'll need
        specs = pixel_mapper.get_render_specs()
        max_width = max(spec.width for spec in specs)
        max_height = max(spec.height for spec in specs)
        
        # Create GPU renderer for context management
        self.gpu_renderer = ShaderRenderer(max_width, max_height)
        self.current_width = max_width
        self.current_height = max_height
        
        # Ensure context is current
        self.gpu_renderer.make_context_current()
        
        # Create VAO for fullscreen quad
        self.vao, self.vbo = create_fullscreen_quad()
        
        # Create uniform sources (same as UnifiedRenderer)
        mapper_camera = getattr(pixel_mapper, 'camera', None)
        self.camera_source = CameraUniformSource(mapper_camera, input_manager)
        self.param_source = ParameterUniformSource(input_manager, audio_mapping_source)
        
        # Store additional uniform sources
        self.uniform_sources = uniform_sources or []
        self._debug_state: Dict[str, Any] = {
            'params': [0.0] * 8,
            'beat_phase': 0.0,
            'beat_pulse': 0.0,
        }
        
        # Create DAG
        self.dag = DAG()
        
        # Store nodes for each render spec
        self.source_nodes: List[SourceNode] = []
        self.current_shader_program = None
        self.shader_path = None
        self.shader_textures: Dict[int, int] = {}  # channel -> texture_id

        # Effect management
        self.effect_nodes: List[EffectNode] = []  # Active effect nodes (one per render spec)
        self.effect_node_map: Dict[str, List[EffectNode]] = {}  # Maps effect name -> nodes
        self.effect_manager = EffectManager(self)
        
        # Load effects from config file
        effect_definitions = load_effect_config()
        for effect_def in effect_definitions:
            self.effect_manager.add_effect(
                effect_def.action,
                effect_def.shader_path,
                effect_def.trigger_mode,
                effect_def.node_class
            )
        
        # Track time
        self.start_time = time.time()
        self.frame_count = 0
    
    def get_camera_source(self):
        """Get the camera uniform source."""
        return self.camera_source
    
    def make_context_current(self) -> bool:
        """
        Make this renderer's OpenGL context current for the calling thread.
        
        Returns:
            True if context was made current, False otherwise
        """
        return self.gpu_renderer.make_context_current()
    
    def _load_texture(self, image_path: str) -> Optional[int]:
        """Load an image file and create an OpenGL texture."""
        from PIL import Image
        try:
            img = Image.open(image_path).convert('RGB')
            img_data = np.array(img, dtype=np.uint8)
            texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, img.width, img.height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
            glBindTexture(GL_TEXTURE_2D, 0)
            print(f'[DAGRenderer] Loaded texture: {image_path} ({img.width}×{img.height})')
            return texture_id
        except Exception as e:
            print(f'[DAGRenderer] Warning: Failed to load texture {image_path}: {e}')
            return None

    def _load_shader_textures(self, shader_path: str):
        """Load textures for a shader based on naming convention."""
        # Clean up old textures
        for tex_id in self.shader_textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.shader_textures.clear()
        
        shader_dir = Path(shader_path).parent
        shader_name = Path(shader_path).stem
        for channel in range(4):
            for ext in ['', '.png', '.jpg', '.jpeg', '.bmp']:
                texture_path = shader_dir / f'{shader_name}.channel{channel}{ext}'
                if texture_path.exists():
                    texture_id = self._load_texture(str(texture_path))
                    if texture_id is not None:
                        self.shader_textures[channel] = texture_id
                    break

    def load_shader(self, shader_path: str):
        """Load shader file."""
        self.shader_path = shader_path
        
        # Ensure context is current
        self.make_context_current()
        
        glsl_version = self._get_glsl_version()
        
        # Load shader program
        self.current_shader_program = load_shader_program(
            shader_path,
            name="main",
            glsl_version=glsl_version,
            vao=self.vao
        )
        
        # Load textures for this shader
        self._load_shader_textures(shader_path)
        
        # Recreate source nodes with new shader
        self._recreate_source_nodes()
    
    def _get_glsl_version(self) -> str:
        """Get GLSL version based on OpenGL version."""
        try:
            gl_version_str = glGetString(GL_VERSION)
            if gl_version_str:
                version_str = gl_version_str.decode() if isinstance(gl_version_str, bytes) else str(gl_version_str)
                import re
                match = re.match(r'(\d+)\.(\d+)', version_str)
                if match:
                    major = int(match.group(1))
                    minor = int(match.group(2))
                    if major > 4 or (major == 4 and minor >= 1):
                        return "410"
                    elif major > 3 or (major == 3 and minor >= 3):
                        return "330 core"
        except Exception:
            pass
        return "120"
    
    def _recreate_source_nodes(self):
        """Recreate source nodes for current render specs."""
        if not self.current_shader_program:
            return
        
        # Clean up old nodes
        for node in self.source_nodes:
            node.cleanup()
        self.source_nodes.clear()
        self.dag = DAG()
        
        # Create source nodes for each render spec
        render_specs = self.pixel_mapper.get_render_specs()
        for i, spec in enumerate(render_specs):
            node_name = f"source_{i}"
            node = SourceNode(
                node_name,
                self.current_shader_program,
                spec.width,
                spec.height,
                self.vao
            )
            self.source_nodes.append(node)
            self.dag.add_node(node)
        
        # Rebuild active effects
        self.effect_manager.rebuild_active()
    
    def add_input_source(self, source: UniformSource):
        """Add input source (audio, MIDI, etc.)."""
        self.uniform_sources.append(source)
    
    def remove_input_source(self, source: UniformSource):
        """Remove input source."""
        if source in self.uniform_sources:
            self.uniform_sources.remove(source)
    
    def _update_uniforms_in_nodes(self, t: float):
        """Update uniforms in all source nodes from uniform sources."""
        # Update uniform sources
        dt = 0.016  # Approximate delta time
        self.camera_source.update(dt)
        self.param_source.update(dt)
        
        for source in self.uniform_sources:
            if hasattr(source, 'update'):
                source.update(dt)
        
        # Get uniforms from all sources
        all_uniforms = {}
        
        # Camera uniforms
        camera_uniforms = self.camera_source.get_uniforms()
        all_uniforms.update(camera_uniforms)
        
        # Parameter uniforms
        param_uniforms = self.param_source.get_uniforms()
        all_uniforms.update(param_uniforms)
        # Stash debug snapshot for overlay
        self._debug_state = {
            'params': self.param_source.get_param_values(),
            'beat_phase': float(all_uniforms.get('iBeatPhase', 0.0)),
            'beat_pulse': float(all_uniforms.get('iBeatPulse', 0.0)),
        }
        
        # Additional uniform sources
        for source in self.uniform_sources:
            if hasattr(source, 'get_uniforms'):
                source_uniforms = source.get_uniforms() or {}
                for name, value in source_uniforms.items():
                    # Do not let secondary sources clobber primary params/camera
                    if name.startswith('iParam') and name in all_uniforms:
                        continue
                    if name.startswith('iCamera') and name in all_uniforms:
                        continue
                    all_uniforms.setdefault(name, value)
        
        # Standard uniforms
        all_uniforms['iTime'] = t
        all_uniforms['iFrame'] = self.frame_count
        all_uniforms['iTimeDelta'] = 0.016
        
        # Mouse uniform from gpu_renderer
        if hasattr(self.gpu_renderer, 'mouse_source'):
            mouse_uniforms = self.gpu_renderer.mouse_source.get_uniforms()
            all_uniforms.update(mouse_uniforms)
        
        # Debug axes
        all_uniforms['iDebugAxes'] = 1.0 if self.settings.get('debug_axes', False) else 0.0
        
        # Update uniforms in all source nodes
        for node in self.source_nodes:
            resolution = (float(node.width), float(node.height))
            all_uniforms['iResolution'] = (resolution[0], resolution[1], 1.0)
            
            # Set uniforms in shader
            node.shader.use()
            for name, value in all_uniforms.items():
                node.shader.set_uniform(name, value)
            glUseProgram(0)
        
        return all_uniforms

    def get_debug_state(self) -> Dict[str, Any]:
        """Expose cached debug state (params and beat info) for overlays."""
        return self._debug_state.copy()
    
    def _update_dynamic_textures(self):
        """Update dynamic textures from uniform sources (e.g., video frames)."""
        # Check each uniform source for frame data
        for source in self.uniform_sources:
            if hasattr(source, 'get_frame_data'):
                frame_data = source.get_frame_data()
                if frame_data is not None:
                    # Upload frame as iChannel0 texture
                    self._upload_frame_as_texture(frame_data, channel=0)
    
    def _upload_frame_as_texture(self, frame_data: np.ndarray, channel: int = 0):
        """Upload numpy array as OpenGL texture."""
        try:
            # Ensure data is in RGB format (height, width, 3)
            if len(frame_data.shape) != 3 or frame_data.shape[2] != 3:
                raise ValueError(f"Expected RGB frame (H, W, 3), got shape {frame_data.shape}")
            
            # Ensure data is uint8 and contiguous
            if frame_data.dtype != np.uint8:
                frame_data = (frame_data * 255).astype(np.uint8)
            
            # Ensure data is C-contiguous (no memory gaps)
            frame_data = np.ascontiguousarray(frame_data)
            
            height, width, _ = frame_data.shape
            
            # Create new texture
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            
            # Set texture parameters
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            
            # Set pixel transfer parameters for proper alignment
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
            
            # Upload texture data
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0,
                        GL_RGB, GL_UNSIGNED_BYTE, frame_data)
            
            # Store texture ID (we'll need to bind this to nodes)
            # For now, we'll handle this in the render method
            
        except Exception as e:
            print(f"Error uploading frame texture: {e}")
            import traceback
            traceback.print_exc()

    def render(self) -> np.ndarray:
        """
        Render using current pixel mapping strategy.
        
        Returns:
            Final framebuffer ready for display
        """
        if not self.current_shader_program:
            raise RuntimeError("No shader loaded. Call load_shader() first.")
        
        # Update dynamic textures
        self._update_dynamic_textures()
        
        # Update time
        elapsed = time.time() - self.start_time
        self.frame_count += 1
        
        # Update uniforms in nodes
        uniforms = self._update_uniforms_in_nodes(elapsed)
        
        # Get render specs
        render_specs = self.pixel_mapper.get_render_specs()
        renders = []
        
        # For volumetric/cube mode, temporarily reposition camera for each face
        for i, spec in enumerate(render_specs):
            # Reposition the camera to view from this face
            if len(render_specs) > 1 and hasattr(self.pixel_mapper, 'reposition_camera_for_face'):
                self.pixel_mapper.reposition_camera_for_face(i, self.camera_source)
                # Update uniforms again with new camera
                uniforms = self._update_uniforms_in_nodes(elapsed)
            
            # Get corresponding source node
            if i < len(self.source_nodes):
                node = self.source_nodes[i]
                
                # Render node (textures will be bound in render method)
                resolution = (float(spec.width), float(spec.height))
                node.render(elapsed, resolution, uniforms=uniforms, shader_textures=self.shader_textures)
                
                # Apply active effects chain (if any)
                output_texture = node.output_texture
                effect_chains = self.effect_manager.get_active_chains(len(self.source_nodes))
                if i < len(effect_chains):
                    for fx in effect_chains[i]:
                        fx.input_texture = output_texture
                        fx.render(elapsed, resolution, uniforms=uniforms)
                        output_texture = fx.output_texture
                
                # Read texture to numpy array
                if output_texture and output_texture.color_texture:
                    pixels = read_texture_to_numpy(
                        output_texture.color_texture,
                        spec.width,
                        spec.height
                    )
                    renders.append(pixels)
                else:
                    # Create a black frame if texture is missing
                    print(f"Warning: No output texture for render spec {i}, creating black frame")
                    renders.append(np.zeros((spec.height, spec.width, 3), dtype=np.uint8))
        
        # Clear camera override after all faces rendered
        if len(render_specs) > 1:
            self.camera_source.set_override_vectors(None)
        
        # Safety check: ensure we have at least one render
        if not renders:
            print("Error: No renders produced, creating default black frame")
            default_spec = render_specs[0] if render_specs else RenderSpec(512, 256, None)
            renders.append(np.zeros((default_spec.height, default_spec.width, 3), dtype=np.uint8))
        
        # Layout all renders into final framebuffer
        return self.pixel_mapper.layout_renders(renders)
    
    def cleanup(self):
        """Clean up GPU resources."""
        # Clean up nodes
        for node in self.source_nodes:
            node.cleanup()
        self.source_nodes.clear()
        self.dag.cleanup()
        if hasattr(self, 'effect_manager'):
            try:
                self.effect_manager.cleanup()
            except Exception:
                pass
        
        # Clean up shader textures
        for tex_id in self.shader_textures.values():
            if tex_id is not None:
                glDeleteTextures([tex_id])
        self.shader_textures.clear()
        
        # Clean up VAO/VBO
        if hasattr(self, 'vao') and self.vao:
            glDeleteVertexArrays(1, [self.vao])
        if hasattr(self, 'vbo') and self.vbo:
            glDeleteBuffers(1, [self.vbo])
        
        # Clean up GPU renderer
        self.gpu_renderer.cleanup()
    
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