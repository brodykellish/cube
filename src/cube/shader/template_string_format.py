"""
Python String Formatting Template System

Pros:
- Simple implementation (~50 lines)
- No shader parser needed
- Works immediately with existing system
- Easy parameter injection
- Fast processing

Cons:
- Double braces {{}} in GLSL code (for literal braces)
- No syntax highlighting for placeholders in editor
- All includes resolved at generation time
- Harder to debug generated shader
"""

from pathlib import Path
from typing import Dict, Any


class StringFormatTemplateEngine:
    """Template engine using Python string formatting."""

    def __init__(self, lib_path: Path = None):
        if lib_path is None:
            lib_path = Path(__file__).parent / "glsl_lib"
        self.lib_path = lib_path
        self.snippets = {}
        self._load_snippets()

    def _load_snippets(self):
        """Load all GLSL snippet files."""
        snippet_dir = self.lib_path / "snippets"
        if not snippet_dir.exists():
            return

        for glsl_file in snippet_dir.glob("*.glsl"):
            with open(glsl_file) as f:
                self.snippets[glsl_file.stem] = f.read()

    def create_shader(self, template_name: str, **params) -> str:
        """
        Create a shader from template with parameters.

        Args:
            template_name: Name of template file (without .glsl)
            **params: Parameters to inject into template

        Returns:
            Complete GLSL shader code
        """
        # Load template
        template_path = self.lib_path / "templates_string" / f"{template_name}.glsl"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(template_path) as f:
            template = f.read()

        # Prepare include substitutions
        includes = {
            f"INCLUDE_{name.upper()}": code
            for name, code in self.snippets.items()
        }

        # Merge with user params
        all_params = {**includes, **params}

        # Format template
        try:
            shader_code = template.format(**all_params)
        except KeyError as e:
            raise ValueError(f"Missing template parameter: {e}")

        return shader_code

    def list_templates(self) -> list[str]:
        """List available template names."""
        template_dir = self.lib_path / "templates_string"
        if not template_dir.exists():
            return []
        return [f.stem for f in template_dir.glob("*.glsl")]

    def list_snippets(self) -> list[str]:
        """List available snippet names."""
        return list(self.snippets.keys())
