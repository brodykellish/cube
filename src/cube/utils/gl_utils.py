"""
OpenGL utility functions for cube.

Provides helpers for common OpenGL operations like creating
fullscreen quads for rendering.
"""
from OpenGL.GL import (  # type: ignore[import-untyped]
    GL_ARRAY_BUFFER,
    GL_FLOAT,
    GL_STATIC_DRAW,
    GL_TRIANGLE_STRIP,
    glBindBuffer,
    glBindVertexArray,
    glBufferData,
    glDrawArrays,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenVertexArrays,
    glVertexAttribPointer,
)
import numpy as np

def create_fullscreen_quad() -> tuple[int, int]:
    """
    Create VAO and VBO for a fullscreen quad.
    
    Returns:
        Tuple of (vao, vbo) handles
    """
    vertices = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32)
    vao = glGenVertexArrays(1)
    vbo = glGenBuffers(1)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 2, GL_FLOAT, False, 0, None)
    glBindVertexArray(0)
    glBindBuffer(GL_ARRAY_BUFFER, 0)
    return (vao, vbo)

def draw_fullscreen_quad(vao: int):
    """
    Draw a fullscreen quad using the provided VAO.
    
    Args:
        vao: Vertex array object handle
    """
    glBindVertexArray(vao)
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
    glBindVertexArray(0)