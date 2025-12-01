"""
Platform-aware shader renderer factory.

This module automatically detects the platform and imports the appropriate
shader renderer implementation:
- MacOS: GLUTShaderRenderer (offscreen rendering)
- Linux/Raspberry Pi: EGLShaderRenderer (headless rendering)

Both implementations provide offscreen rendering suitable for compositing
into a display system (e.g., cube_control.py).

Usage:
    from piomatter.shader.shader_renderer import ShaderRenderer
    
    renderer = ShaderRenderer(width=64, height=64)
    renderer.load_shader("shader.glsl")
    renderer.render()
    pixels = renderer.read_pixels()
"""

import platform


def create_shader_renderer(width: int, height: int, **kwargs):
    """
    Create platform-appropriate shader renderer.
    
    Args:
        width: Render width in pixels
        height: Render height in pixels
        **kwargs: Additional platform-specific arguments (ignored, kept for compatibility)
    
    Returns:
        Platform-appropriate shader renderer instance
    """
    system = platform.system()
    
    if system == 'Darwin':
        from .shader_renderer_glut import GLUTShaderRenderer
        print(f"Detected MacOS - using GLUT renderer (offscreen)")
        return GLUTShaderRenderer(width, height)
    
    elif system == 'Linux':
        from .shader_renderer_egl import EGLShaderRenderer
        print(f"Detected Linux - using EGL renderer (headless)")
        return EGLShaderRenderer(width, height)
    
    else:
        raise RuntimeError(
            f"Unsupported platform: {system}. "
            "Shader renderer only supports MacOS (GLUT) and Linux (EGL)."
        )


ShaderRenderer = create_shader_renderer


__all__ = ['ShaderRenderer', 'create_shader_renderer']
