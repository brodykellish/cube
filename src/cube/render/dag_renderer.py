"""
Stateless DAG renderer for cube.

Takes a DAG and renders it. That's it.
"""
import numpy as np
import time
from typing import Optional, Dict, Any, Callable
from OpenGL.GL import *

from cube.shader.shader_loader import load_shader_program
from cube.dag.dag import DAG
from cube.dag.effect_node import EffectNode
from cube.dag.source_node import SourceNode
from cube.dag.video_source_node import VideoSourceNode
from cube.utils.gl_utils import create_fullscreen_quad
from cube.utils.texture_utils import read_texture_to_numpy
from .pixel_mappers import PixelMapper, RenderSpec
from .parameter_store import ParameterStore


class DAGRenderer:
    """Stateless DAG renderer."""
    
    def __init__(self, pixel_mapper: PixelMapper,
                 make_context_current: Optional[Callable[[], bool]] = None):
        """
        Initialize DAG renderer.
        
        Args:
            pixel_mapper: PixelMapper for layout
            make_context_current: Optional function to make OpenGL context current
        """
        self.pixel_mapper = pixel_mapper
        self._make_context_current_fn = make_context_current
        
        # Max dimensions
        specs = pixel_mapper.get_render_specs()
        max_width = max(spec.width for spec in specs)
        max_height = max(spec.height for spec in specs)
        
        # Make context current
        if self._make_context_current_fn:
            if not self._make_context_current_fn():
                raise RuntimeError("Failed to make OpenGL context current")
        else:
            from cube.shader import ShaderRenderer
            self.gpu_renderer = ShaderRenderer(max_width, max_height)
            if not self.gpu_renderer.make_context_current():
                raise RuntimeError("Failed to make OpenGL context current")
        
        # Create VAO
        self.vao, self.vbo = create_fullscreen_quad()
        
        self._debug_state: Dict[str, Any] = {
            'params': [0.0] * 8,
            'beat_phase': 0.0,
            'beat_pulse': 0.0,
        }
    
    def make_context_current(self) -> bool:
        """Make OpenGL context current."""
        if self._make_context_current_fn:
            return self._make_context_current_fn()
        elif hasattr(self, 'gpu_renderer'):
            return self.gpu_renderer.make_context_current()
        return False
    
    def _get_glsl_version(self) -> str:
        """Get GLSL version."""
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
    
    def get_glsl_version(self) -> str:
        """Public method to get GLSL version."""
        return self._get_glsl_version()
    
    
    def render(self, dag: DAG, parameters: ParameterStore) -> np.ndarray:
        """
        Render a DAG with parameters.
        
        Args:
            dag: DAG to render
            parameters: ParameterStore with all parameter values (already updated)
            
        Returns:
            Final framebuffer
            
        Note: Parameters should be updated BEFORE calling render().
        This method only reads from ParameterStore, it does not update it.
        """
        if not dag or not dag.nodes:
            raise RuntimeError("DAG is empty")
        
        # Get all parameters for rendering
        all_params = parameters.get_all_parameters()
        
        # Render all nodes in topological order
        sorted_nodes = dag.topological_sort()
        if parameters.frame_count == 1:
            print(f"[DAGRenderer] Rendering {len(sorted_nodes)} nodes in topological order")
            for i, node in enumerate(sorted_nodes):
                print(f"  {i+1}. {node.name} ({type(node).__name__})")
        
        t = time.time() - parameters.start_time
        
        for node in sorted_nodes:
            if not node.enabled:
                continue
            
            # Get parameters for this node
            node_params = parameters.get_parameters_for_node(node)
            resolution = (float(node.width), float(node.height))
            
            # Render node with parameters
            if isinstance(node, EffectNode):
                # Effect nodes resolve inputs from DAG
                node.render(t, resolution, uniforms=node_params, dag=dag)
            elif isinstance(node, SourceNode):
                # Source nodes (shader-based) - they load their own textures
                node.render(t, resolution, uniforms=node_params)
            elif isinstance(node, VideoSourceNode):
                # Video source nodes
                node.render(t, resolution, uniforms=node_params)
            else:
                # Generic node
                node.render(t, resolution)
        
        # Extract outputs per render spec
        render_specs = self.pixel_mapper.get_render_specs()
        renders = []
        
        for i, spec in enumerate(render_specs):
            # Note: Camera repositioning for cube faces would need to be handled
            # by updating camera parameters in ParameterStore before render
            # For now, we'll skip this complexity
            
            # Find source node for this spec (root nodes)
            source_nodes = dag.root_nodes
            if i < len(source_nodes):
                source = source_nodes[i]
            else:
                source = source_nodes[0] if source_nodes else None
            
            if not source:
                renders.append(np.zeros((spec.height, spec.width, 3), dtype=np.uint8))
                continue
            
            # Find final output (walk chain via children)
            output_node = source
            while output_node.children:
                # Take first child (for now)
                output_node = output_node.children[0]
            
            # Read texture
            if output_node.output_texture and output_node.output_texture.color_texture:
                pixels = read_texture_to_numpy(
                    output_node.output_texture.color_texture,
                    spec.width,
                    spec.height
                )
                renders.append(pixels)
            else:
                renders.append(np.zeros((spec.height, spec.width, 3), dtype=np.uint8))
        
        if not renders:
            default_spec = render_specs[0] if render_specs else RenderSpec(512, 256, None)
            renders.append(np.zeros((default_spec.height, default_spec.width, 3), dtype=np.uint8))
        
        return self.pixel_mapper.layout_renders(renders)
    
    def get_debug_state(self, parameters: ParameterStore) -> Dict[str, Any]:
        """Get debug state from parameters."""
        params = parameters.get_all_parameters()
        return {
            'params': [params.get(f'iParam{i}', 0.0) for i in range(8)],
            'beat_phase': float(params.get('iBeatPhase', 0.0)),
            'beat_pulse': float(params.get('iBeatPulse', 0.0)),
        }
    
    def cleanup(self):
        """Clean up resources."""
        # Clean up VAO/VBO
        if hasattr(self, 'vao') and self.vao:
            glDeleteVertexArrays(1, [self.vao])
        if hasattr(self, 'vbo') and self.vbo:
            glDeleteBuffers(1, [self.vbo])
        
        if hasattr(self, 'gpu_renderer'):
            self.gpu_renderer.cleanup()
