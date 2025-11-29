#!/usr/bin/env python3
"""
Automated GLSL shader fixer for GLSL 1.20 compatibility.
"""
import sys
import re
from pathlib import Path

def fix_shader(shader_path: Path) -> tuple[bool, list[str]]:
    """
    Fix common GLSL 1.20 compatibility issues in shader.

    Returns:
        (changed, fixes_applied)
    """
    fixes = []

    with open(shader_path, 'r') as f:
        content = f.read()

    original = content

    # Fix 1: Remove standalone precision qualifiers
    if re.search(r'^precision\s+(lowp|mediump|highp)\s+float\s*;', content, re.MULTILINE):
        content = re.sub(r'^precision\s+(lowp|mediump|highp)\s+float\s*;', '', content, flags=re.MULTILINE)
        fixes.append("Removed standalone precision qualifiers")

    # Fix 2: Replace textureLod with texture2D (GLSL 1.20 doesn't have textureLod without extension)
    if 'textureLod' in content and '#extension' not in content:
        # Simple replacement for common case
        content = re.sub(r'textureLod\s*\(\s*(\w+)\s*,\s*([^,]+),\s*0\.0\s*\)', r'texture2D(\1, \2)', content)
        fixes.append("Replaced textureLod() with texture2D()")

    # Fix 3: Replace bit shift operations in #define or simple expressions
    # Pattern: (x>>1) becomes floor(x/2.0)
    # Pattern: (x&1) becomes int(mod(float(x), 2.0))
    if '>>' in content or '&' in content:
        # This is complex, need to handle case-by-case
        # For now, flag it
        fixes.append("WARNING: Contains bit operations (>> or &), may need manual fix")

    if content != original:
        # Add changelog comment at top
        changelog = f"// FIXED for GLSL 1.20 compatibility: {', '.join(fixes)}\n//\n"
        content = changelog + content

        with open(shader_path, 'w') as f:
            f.write(content)

        return True, fixes

    return False, []

def main():
    """Fix all failing shaders."""
    failing_shaders = [
        'clouds2.glsl',
        'fluff.glsl',
        'happy_jump.glsl',
        'lights.glsl',
        'mandle_brot2.glsl',
        'soap_bubbles.glsl',
        'spiral1.glsl',
        'trippy.glsl',
        'voxel1.glsl',
        'wretched.glsl'
    ]

    shaders_dir = Path(__file__).parent / 'shaders'

    for shader_name in failing_shaders:
        shader_path = shaders_dir / shader_name
        if not shader_path.exists():
            print(f"❌ {shader_name}: Not found")
            continue

        changed, fixes = fix_shader(shader_path)
        if changed:
            print(f"✓ {shader_name}: {', '.join(fixes)}")
        else:
            print(f"- {shader_name}: No automatic fixes available, needs manual inspection")

if __name__ == '__main__':
    main()
