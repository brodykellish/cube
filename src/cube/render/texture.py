"""
Texture and framebuffer management for cube.

Provides Texture class for managing FBOs and render targets.
"""
from typing import Optional
from OpenGL.GL import *

class Texture:
    """
    Texture with associated framebuffer object.
    
    Used as render targets for nodes in the DAG.
    """

    def __init__(self, width: int, height: int):
        """
        Initialize texture.
        
        Args:
            width: Texture width in pixels
            height: Texture height in pixels
        """
        self.width = width
        self.height = height
        self.fbo = None
        self.color_texture = None
        self.depth_buffer = None
        self._created = False

    def create(self):
        """Create FBO and texture."""
        if self._created:
            return
        self.color_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.color_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        self.depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_buffer)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, self.width, self.height)
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.color_texture, 0)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth_buffer)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f'Framebuffer incomplete: {status}')
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glBindRenderbuffer(GL_RENDERBUFFER, 0)
        self._created = True

    def bind(self):
        """Bind FBO for rendering."""
        if not self._created:
            self.create()
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.width, self.height)

    def unbind(self):
        """Unbind FBO."""
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def cleanup(self):
        """Delete OpenGL resources."""
        if self.fbo is not None:
            glDeleteFramebuffers(1, [self.fbo])
            self.fbo = None
        if self.color_texture is not None:
            glDeleteTextures(1, [self.color_texture])
            self.color_texture = None
        if self.depth_buffer is not None:
            glDeleteRenderbuffers(1, [self.depth_buffer])
            self.depth_buffer = None
        self._created = False