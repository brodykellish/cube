# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/template_include_preprocessor.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-03 02:12:46 UTC (1764727966)

"""
GLSL #include Preprocessor Template System

Pros:
- Native GLSL syntax (#include)
- Better syntax highlighting in editors
- Can debug included files separately
- More "standard" approach
- Cleaner template code (no double braces)

Cons:
- More complex implementation (~150 lines)
- Need to implement preprocessor
- Recursive include handling
- Include path resolution
- Circular dependency detection needed
"""
from pathlib import Path
from typing import Dict, Set, List, Any
import re

class IncludePreprocessor:
    """GLSL preprocessor that handles #include directives."""

    def __init__(self, lib_path: Path=None):
        if lib_path is None:
            lib_path = Path(__file__).parent / 'glsl_lib'
        self.lib_path = lib_path
        self.snippet_dir = lib_path / 'snippets'
        self.include_pattern = re.compile('^\\s*#include\\s+"([^"]+)"\\s*$', re.MULTILINE)

    def process_includes(self, source: str, included: Set[str]=None) -> str:
        """
        Recursively process #include directives.

        Args:
            source: GLSL source code with #include directives
            included: Set of already included files (for circular dependency detection)

        Returns:
            GLSL source with all includes resolved
        """
        if included is None:
            included = set()

        def replace_include(match):
            include_file = match.group(1)
            if include_file in included:
                raise ValueError(f'Circular include detected: {include_file}')
            include_path = self.snippet_dir / include_file
            if not include_path.exists():
                raise FileNotFoundError(f'Include file not found: {include_path}')
            with open(include_path) as f:
                include_source = f.read()
            new_included = included | {include_file}
            return self.process_includes(include_source, new_included)
        return self.include_pattern.sub(replace_include, source)

    def process_defines(self, source: str, defines: Dict[str, Any]) -> str:
        """
        Replace #define constants with actual values.

        Args:
            source: GLSL source code
            defines: Dictionary of define name -> value

        Returns:
            GLSL source with defines replaced
        """
        for name, value in defines.items():
            pattern = re.compile(f'^\\s*#define\\s+{re.escape(name)}\\s+.*$', re.MULTILINE)
            replacement = f'#define {name} {value}'
            source = pattern.sub(replacement, source)
        return source

class IncludeTemplateEngine:
    """Template engine using GLSL #include directives."""

    def __init__(self, lib_path: Path=None):
        if lib_path is None:
            lib_path = Path(__file__).parent / 'glsl_lib'
        self.lib_path = lib_path
        self.preprocessor = IncludePreprocessor(lib_path)

    def create_shader(self, template_name: str, **params) -> str:
        """
        Create a shader from template with parameters.

        Args:
            template_name: Name of template file (without .glsl)
            **params: Parameters to override #define values

        Returns:
            Complete GLSL shader code
        """
        template_path = self.lib_path / 'templates_include' / f'{template_name}.glsl'
        if not template_path.exists():
            raise FileNotFoundError(f'Template not found: {template_path}')
        with open(template_path) as f:
            template = f.read()
        shader_code = self.preprocessor.process_includes(template)
        if params:
            shader_code = self.preprocessor.process_defines(shader_code, params)
        return shader_code

    def list_templates(self) -> List[str]:
        """List available template names."""
        template_dir = self.lib_path / 'templates_include'
        if not template_dir.exists():
            return []
        return [f.stem for f in template_dir.glob('*.glsl')]

    def list_snippets(self) -> List[str]:
        """List available snippet names."""
        if not self.preprocessor.snippet_dir.exists():
            return []
        return [f.stem for f in self.preprocessor.snippet_dir.glob('*.glsl')]