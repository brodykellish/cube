"""
Minimal shader template engine using Python string formatting.
"""

from pathlib import Path
from typing import Dict, Optional


class ShaderTemplateEngine:
    """Minimal template engine for generating shaders from reusable components."""

    def __init__(self):
        self.lib_path = Path(__file__).parent / "glsl_lib"
        self.components = self._load_components()

    def _load_components(self) -> Dict[str, str]:
        """Load reusable GLSL components."""
        components = {}
        snippets_dir = self.lib_path / "snippets"

        if snippets_dir.exists():
            for glsl_file in snippets_dir.glob("*.glsl"):
                components[glsl_file.stem.upper()] = glsl_file.read_text()

        return components

    def generate(self, primitive: str, **params) -> str:
        """Generate a shader for a geometric primitive."""
        template_path = self.lib_path / "primitives" / f"{primitive}.glsl"

        if not template_path.exists():
            raise FileNotFoundError(f"Primitive template not found: {primitive}")

        template = template_path.read_text()

        # Merge components and parameters
        context = {f"INCLUDE_{k}": v for k, v in self.components.items()}
        context.update(params)

        return template.format(**context)

    def list_primitives(self) -> list:
        """List available geometric primitives."""
        primitives_dir = self.lib_path / "primitives"
        if not primitives_dir.exists():
            return []
        return sorted([f.stem for f in primitives_dir.glob("*.glsl")])