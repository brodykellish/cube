"""
Texture utility functions for cube.

Provides helpers for reading textures and converting to numpy arrays.
"""

import numpy as np
from OpenGL.GL import *


def read_texture_to_numpy(texture_id: int, width: int, height: int) -> np.ndarray:
    """
    Read an OpenGL texture to a numpy array.
    
    Args:
        texture_id: OpenGL texture ID
        width: Texture width
        height: Texture height
        
    Returns:
        Numpy array of shape (height, width, 3) with dtype uint8
    """
    # Bind texture
    glBindTexture(GL_TEXTURE_2D, texture_id)
    
    # Read pixels from texture
    # We need to bind the texture to a framebuffer to read it
    fbo = glGenFramebuffers(1)
    glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo)
    glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture_id, 0)
    
    # Allocate buffer for pixels (RGBA format)
    pixels = np.zeros((height, width, 4), dtype=np.uint8)
    
    # Read pixels
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels)
    
    # Cleanup
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
    glDeleteFramebuffers(1, [fbo])
    glBindTexture(GL_TEXTURE_2D, 0)
    
    # Convert RGBA to RGB
    rgb = pixels[:, :, :3]
    
    # Flip vertically (OpenGL reads from bottom-left, we want top-left)
    rgb = np.flip(rgb, axis=0).copy()
    
    return rgb


def read_fbo_to_numpy(fbo: int, width: int, height: int) -> np.ndarray:
    """
    Read a framebuffer object to a numpy array.
    
    Args:
        fbo: OpenGL framebuffer object ID
        width: Framebuffer width
        height: Framebuffer height
        
    Returns:
        Numpy array of shape (height, width, 3) with dtype uint8
    """
    # Bind framebuffer
    glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo)
    
    # Allocate buffer for pixels (RGBA format)
    pixels = np.zeros((height, width, 4), dtype=np.uint8)
    
    # Read pixels
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels)
    
    # Unbind framebuffer
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
    
    # Convert RGBA to RGB
    rgb = pixels[:, :, :3]
    
    # Flip vertically (OpenGL reads from bottom-left, we want top-left)
    rgb = np.flip(rgb, axis=0).copy()
    
    return rgb
