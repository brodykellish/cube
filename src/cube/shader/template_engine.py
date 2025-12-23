# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/template_engine.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-03 22:06:01 UTC (1764799561)

"""
Simple shader loader for primitives (no templating).
"""
from pathlib import Path
from typing import List

class ShaderTemplateEngine:
    """Simple loader for primitive shaders (no templating)."""

    def __init__(self):
        self.shader_root = Path(__file__).parent.parent.parent.parent / 'shaders'
        self.primitives_path = self.shader_root / 'primitives'

    def generate(self, primitive: str, **params) -> str:
        """
        Load a primitive shader (no code generation, just file read).

        Args:
            primitive: Name of primitive (sphere, box, torus, plane)
            **params: Ignored (no templating)

        Returns:
            Raw GLSL code from file
        """
        shader_path = self.primitives_path / f'{primitive}.glsl'
        if not shader_path.exists():
            raise FileNotFoundError(f'Primitive not found: {shader_path}')
        return shader_path.read_text()

    def list_primitives(self) -> List[str]:
        """List available geometric primitives."""
        if not self.primitives_path.exists():
            return []
        return sorted([f.stem for f in self.primitives_path.glob('*.glsl')])