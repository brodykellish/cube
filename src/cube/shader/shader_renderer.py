"""
Platform-aware shader renderer factory.

This module automatically detects the platform and imports the appropriate
shader renderer implementation:
- MacOS: PygletShaderRendererFBO (modern OpenGL, offscreen via FBO)
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
        # Use modern pyglet-based FBO renderer on macOS.
        from .shader_renderer_pyglet_fbo import PygletShaderRendererFBO

        print("Detected MacOS - using Pyglet FBO renderer (modern OpenGL)")
        return PygletShaderRendererFBO(width, height)
    
    if system == 'Linux':
        from .shader_renderer_egl import EGLShaderRenderer

        print("Detected Linux - using EGL renderer (headless)")
        return EGLShaderRenderer(width, height)
    
        raise RuntimeError(
            f"Unsupported platform: {system}. "
        "Shader renderer only supports MacOS (pyglet FBO) and Linux (EGL)."
        )


ShaderRenderer = create_shader_renderer


__all__ = ['ShaderRenderer', 'create_shader_renderer']
