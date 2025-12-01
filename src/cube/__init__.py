"""
Cube - LED Cube Control System
===============================

High-level control system for LED cube displays with menu system,
shader rendering, and display backends.

Main Classes:
- CubeController: Main controller for the LED cube system

Submodules:
- cube.display: Display backend system (pygame/piomatter)
- cube.input: Input handling system
- cube.menu: Menu system components
- cube.shader: GLSL shader rendering system
- cube.volumetric: Volumetric 3D cube rendering
"""

from .controller import CubeController

__all__ = ['CubeController', 'display', 'input', 'menu', 'shader', 'volumetric']
