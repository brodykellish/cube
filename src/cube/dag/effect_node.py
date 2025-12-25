"""
Effect node implementation for cube.

EffectNode consumes one texture and outputs one texture.
"""
from typing import Optional, Dict, Any
from pathlib import Path
import random
import numpy as np
import traceback
from OpenGL.GL import *
from PIL import Image
from .node import Node
from ..shader.program import ShaderProgram
from ..shader.shader_loader import load_shader_program
from ..render.texture import Texture
from ..utils.gl_utils import draw_fullscreen_quad


class EffectNode(Node):
    """
    Effect node that processes a single input texture.
    
    Used for effects like blur, bloom, warp, etc.
    """

    def __init__(self, name: str, shader: ShaderProgram, input_texture: Texture, width: int, height: int, vao: int):
        """
        Initialize effect node.
        
        Args:
            name: Node identifier
            shader: Shader program
            input_texture: Input texture to process
            width: Output width
            height: Output height
            vao: VAO for fullscreen quad
        """
        super().__init__(name, shader, width, height)
        self.input_texture = input_texture
        self.vao = vao
        self.additional_textures = {}

    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None):
        """
        Render effect node.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
            uniforms: Optional dictionary of uniforms to set (overrides defaults)
        """
        if not self.enabled:
            return
        
        self.output_texture.bind()
        # Ensure clear color is black (not white from other contexts)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.shader.use()

        if uniforms:
            for name, value in uniforms.items():
                self.shader.set_uniform(name, value)
        
        if self.input_texture.color_texture:
            self.shader.set_texture('iChannel0', 0, self.input_texture.color_texture)
        
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

    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None):
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
        
        super().render(t, resolution, uniforms)
        self._copy_current_to_previous()

    def cleanup(self):
        """Clean up previous frame resources."""
        if self.previous_frame_fbo is not None:
            glDeleteFramebuffers(1, [self.previous_frame_fbo])
            self.previous_frame_fbo = None
        self._previous_frame_initialized = False
        super().cleanup()
