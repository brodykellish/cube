"""
Effect node implementation for cube.

EffectNode consumes one texture and outputs one texture.
"""
from typing import Optional
from pathlib import Path
import random
import math
import numpy as np
import traceback
from OpenGL.GL import *
from PIL import Image
from .node import Node
from ..shader.program import ShaderProgram
from ..render.texture import Texture
from ..utils.gl_utils import draw_fullscreen_quad
from .dag import DAG


class EffectNode(Node):
    """
    Effect node that processes a single input texture.
    
    Used for effects like blur, bloom, warp, etc.
    """

    def __init__(self, name: str, shader: ShaderProgram, input_texture: Optional[Texture] = None, width: int = 0, height: int = 0, vao: int = 0):
        """
        Initialize effect node.
        
        Args:
            name: Node identifier
            shader: Shader program
            input_texture: Optional input texture (can be resolved from DAG connections)
            width: Output width (required if input_texture not provided)
            height: Output height (required if input_texture not provided)
            vao: VAO for fullscreen quad
        """
        # If input_texture provided, use its dimensions
        if input_texture is not None:
            width = input_texture.width
            height = input_texture.height
        
        super().__init__(name, shader, width, height)
        self.input_texture = input_texture  # May be None, resolved from DAG during render
        self.vao = vao
        self.additional_textures = {}
        self._dag = None  # Set by renderer to allow input resolution

    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None, dag: Optional[DAG] = None):
        """
        Render effect node.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
            uniforms: Optional dictionary of uniforms to set (overrides defaults)
            dag: Optional DAG instance (unused, kept for API compatibility)
        """
        if not self.enabled:
            return
        
        # Resolve input texture from parent node if not set
        input_texture = self.input_texture
        if input_texture is None:
            if self.parent:
                input_texture = self.parent.output_texture
        
        # If still no input texture, skip rendering
        if input_texture is None:
            return
        
        self.output_texture.bind()
        # Ensure clear color is black (not white from other contexts)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.shader.use()

        if uniforms:
            for name, value in uniforms.items():
                self.shader.set_uniform(name, value)
        
        if input_texture.color_texture:
            self.shader.set_texture('iChannel0', 0, input_texture.color_texture)
        
        texture_unit = 1
        for channel_name, texture_id in self.additional_textures.items():
            if texture_id:
                self.shader.set_texture(channel_name, texture_unit, texture_id)
                texture_unit += 1
        
        draw_fullscreen_quad(self.vao)
        glUseProgram(0)
        self.output_texture.unbind()

    def update_input_texture(self, input_texture: Texture):
        """
        Update the input texture reference without recreating the node.
        
        Args:
            input_texture: New input texture to use
        """
        self.input_texture = input_texture

    def cleanup(self):
        """Clean up additional textures."""
        for channel_name, texture_id in self.additional_textures.items():
            if texture_id:
                glDeleteTextures([texture_id])
        self.additional_textures.clear()
        super().cleanup()


class ImageFlashEffectNode(EffectNode):
    """
    Specialized effect node for image flash effect.
    
    Handles loading and displaying random images from images/flash/ directory.
    """
    SHADER_PATH = 'shaders/effects/image_flash.glsl'

    def __init__(self, name: str, shader: ShaderProgram, input_texture: Texture, width: int, height: int, vao: int):
        """Initialize image flash effect node."""
        super().__init__(name, shader, input_texture, width, height, vao)
        self._setup_image_flash()

    def _setup_image_flash(self):
        """Setup image flash effect: load images and prepare texture."""
        project_root = Path(__file__).parent.parent.parent.parent
        self.flash_images_dir = project_root / 'images' / 'flash'
        self.flash_images = []
        self.current_flash_image_index = 0
        
        if self.flash_images_dir.exists():
            for ext in ['png', 'PNG', 'jpg', 'JPG', 'jpeg', 'JPEG']:
                self.flash_images.extend(sorted(self.flash_images_dir.glob(f'*.{ext}')))
        
        if self.flash_images:
            self._select_random_flash_image()
            self._load_flash_image_texture()

    def _select_random_flash_image(self):
        """Select a random flash image."""
        if not self.flash_images:
            return
        self.current_flash_image_index = random.randint(0, len(self.flash_images) - 1)

    def _load_flash_image_texture(self):
        """Load the current flash image as a texture."""
        if not self.flash_images or self.current_flash_image_index >= len(self.flash_images):
            return None
        
        image_path = self.flash_images[self.current_flash_image_index]
        try:
            img = Image.open(image_path).convert('RGB')
            img_data = np.array(img, dtype=np.uint8)
            img_data = np.flip(img_data, axis=0).copy()
            img_data = np.ascontiguousarray(img_data)
            height, width, _ = img_data.shape
            
            if 'iChannel1' in self.additional_textures and self.additional_textures['iChannel1']:
                glDeleteTextures([self.additional_textures['iChannel1']])
            
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
            glFlush()
            glBindTexture(GL_TEXTURE_2D, 0)
            self.additional_textures['iChannel1'] = tex_id
        except Exception as e:
            print(f'[ImageFlashEffectNode] Failed to load flash image {image_path.name}: {e}')
            traceback.print_exc()

    def refresh_flash_image(self):
        """Select a new random flash image and reload texture. Call this when effect is activated."""
        if self.flash_images:
            self._select_random_flash_image()
            self._load_flash_image_texture()


class FrameDifferencingEffectNode(EffectNode):
    """
    Specialized effect node for frame differencing effect.
    
    Maintains a previous frame buffer and feeds it to iChannel1 for comparison.
    """

    def __init__(self, name: str, shader: ShaderProgram, input_texture: Texture, width: int, height: int, vao: int):
        """Initialize frame differencing effect node."""
        super().__init__(name, shader, input_texture, width, height, vao)
        self.previous_frame_texture = None
        self.previous_frame_fbo = None
        self._previous_frame_initialized = False

    def _create_previous_frame_buffer(self, width: int, height: int):
        """Create texture and FBO for storing previous frame."""
        if self._previous_frame_initialized:
            return
        
        self.previous_frame_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.previous_frame_texture)
        black_data = np.zeros((height, width, 4), dtype=np.uint8)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, black_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        
        self.previous_frame_fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.previous_frame_fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.previous_frame_texture, 0)
        
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f'Previous frame FBO incomplete: {status}')
        
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        self.additional_textures['iChannel1'] = self.previous_frame_texture
        self._previous_frame_initialized = True

    def _copy_current_to_previous(self):
        """Copy current output texture to previous frame buffer."""
        if not self._previous_frame_initialized or not self.output_texture.color_texture:
            return None
        
        glFlush()
        glFinish()
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.output_texture.fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.previous_frame_fbo)
        glBlitFramebuffer(0, 0, self.width, self.height, 0, 0, self.width, self.height, GL_COLOR_BUFFER_BIT, GL_NEAREST)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)

    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None, dag: Optional[DAG] = None):
        """
        Render frame differencing effect.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
            uniforms: Optional dictionary of uniforms to set (overrides defaults)
        """
        if not self.enabled:
            return
        
        if not self._previous_frame_initialized:
            self._create_previous_frame_buffer(self.width, self.height)
        
        super().render(t, resolution, uniforms, dag)
        self._copy_current_to_previous()

    def cleanup(self):
        """Clean up previous frame resources."""
        if self.previous_frame_fbo is not None:
            glDeleteFramebuffers(1, [self.previous_frame_fbo])
            self.previous_frame_fbo = None
        self._previous_frame_initialized = False
        super().cleanup()


class MiniatureOverlayEffectNode(EffectNode):
    """
    Specialized effect node for trailing effect with feedback.
    
    Maintains a previous frame buffer (iChannel1) for feedback
    and tracks a direction vector that varies slightly each frame.
    Creates a long trailing tail effect.
    """

    def __init__(self, name: str, shader: ShaderProgram, input_texture: Optional[Texture] = None, width: int = 0, height: int = 0, vao: int = 0):
        """Initialize miniature overlay effect node."""
        super().__init__(name, shader, input_texture, width, height, vao)
        self.previous_frame_texture = None
        self.previous_frame_fbo = None
        self._previous_frame_initialized = False
        
        # Direction vector state (normalized, magnitude 1)
        # Initialized to None - will be set randomly when node is enabled
        self._direction = None
        self._direction_initialized = False

        # Variance parameters
        self._direction_variance = 0.05  # Maximum angle variance per frame (radians)
        self._variance_seed = random.random() * 1000.0  # Seed for variance noise
        
        # Frame skipping for accumulation rate control
        self._frame_count = 0
        self._accumulation_interval = 8  # Only accumulate every 8th frame

    def _create_previous_frame_buffer(self, width: int, height: int):
        """Create texture and FBO for storing previous frame (feedback)."""
        if self._previous_frame_initialized:
            return
        
        self.previous_frame_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.previous_frame_texture)
        black_data = np.zeros((height, width, 4), dtype=np.uint8)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, black_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        
        self.previous_frame_fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.previous_frame_fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.previous_frame_texture, 0)
        
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f'Previous frame FBO incomplete: {status}')
        
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        self.additional_textures['iChannel1'] = self.previous_frame_texture
        self._previous_frame_initialized = True

    def _copy_current_to_previous(self):
        """Copy current output texture to previous frame buffer (feedback)."""
        if not self._previous_frame_initialized or not self.output_texture.color_texture:
            return
        
        glFlush()
        glFinish()
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.output_texture.fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.previous_frame_fbo)
        glBlitFramebuffer(0, 0, self.width, self.height, 0, 0, self.width, self.height, GL_COLOR_BUFFER_BIT, GL_NEAREST)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)

    def _initialize_direction(self):
        """Initialize direction vector to a random direction when node is enabled."""
        if self._direction_initialized:
            return
        
        # Pick random direction
        import math
        angle = random.random() * math.pi * 2.0
        self._direction = [math.cos(angle), math.sin(angle)]
        self._direction_initialized = True
    
    def _update_direction(self, t: float):
        """
        Update direction vector with slight variance each frame.
        
        Maintains constant magnitude of 1, only direction varies.
        """
        if not self._direction_initialized:
            self._initialize_direction()
        
        import math
        
        # Get current angle
        current_angle = math.atan2(self._direction[1], self._direction[0])
        
        # Add slight variance (random walk in angle space)
        variance = (random.random() - 0.5) * 2.0 * self._direction_variance
        new_angle = current_angle + variance
        
        # Update direction vector (normalized to magnitude 1)
        self._direction[0] = math.cos(new_angle)
        self._direction[1] = math.sin(new_angle)

    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None, dag: Optional[DAG] = None):
        """
        Render trailing effect.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
            uniforms: Optional dictionary of uniforms to set (overrides defaults)
        """
        if not self.enabled:
            return
        
        if not self._previous_frame_initialized:
            self._create_previous_frame_buffer(self.width, self.height)
        
        # Initialize direction if not already done
        if not self._direction_initialized:
            self._initialize_direction()
        
        # Update direction with slight variance
        self._update_direction(t)
        
        # Add direction to uniforms (normalized vector, magnitude 1)
        if uniforms is None:
            uniforms = {}
        else:
            uniforms = uniforms.copy()  # Don't modify the original
        
        uniforms['direction'] = tuple(self._direction)
        
        # Render with feedback
        super().render(t, resolution, uniforms, dag)
        
        # Only copy to feedback buffer every 4th frame to slow accumulation
        self._frame_count += 1
        if self._frame_count % self._accumulation_interval == 0:
            self._copy_current_to_previous()

    def cleanup(self):
        """Clean up previous frame resources."""
        if self.previous_frame_fbo is not None:
            glDeleteFramebuffers(1, [self.previous_frame_fbo])
            self.previous_frame_fbo = None
        self._previous_frame_initialized = False
        super().cleanup()
