"""
Shader loader for DAG-based rendering.

Loads shader files and creates ShaderProgram instances with auto-detected specs.
"""

from pathlib import Path
from typing import Optional
from .spec import ShaderSpec, UniformSpec, UniformType
from .program import ShaderProgram


def create_shader_spec_from_program(shader_program: ShaderProgram, name: str) -> ShaderSpec:
    """
    Create a ShaderSpec from an already-compiled ShaderProgram.
    
    This auto-detects uniforms by querying the compiled program.
    
    Args:
        shader_program: Compiled ShaderProgram instance
        name: Shader name
        
    Returns:
        ShaderSpec with detected uniforms
    """
    uniforms = []
    
    # Query all active uniforms from the compiled program
    for uniform_name, location in shader_program.uniform_locations.items():
        # Skip standard Shadertoy uniforms (these are always present)
        standard_uniforms = {
            'iResolution', 'iTime', 'iTimeDelta', 'iFrame', 'iMouse', 'iInput',
            'iChannel0', 'iChannel1', 'iChannel2', 'iChannel3',
            'iCameraPos', 'iCameraRight', 'iCameraUp', 'iCameraForward',
            'iBPM', 'iBeatPhase', 'iBeatPulse', 'iAudioLevel', 'iAudioSpectrum',
            'iDebugAxes', 'iParam0', 'iParam1', 'iParam2', 'iParam3',
            'iParam4', 'iParam5', 'iParam6', 'iParam7'
        }
        
        if uniform_name in standard_uniforms:
            continue
        
        # Try to determine uniform type (default to float)
        # We can't easily determine the exact type from location alone,
        # so we default to float for custom uniforms
        uniform_type = UniformType.FLOAT
        
        # Check if it's a sampler2D (texture)
        if uniform_name.startswith('iChannel') or 'texture' in uniform_name.lower():
            uniform_type = UniformType.SAMPLER2D
        
        uniforms.append(UniformSpec(
            name=uniform_name,
            type=uniform_type,
            min=0.0,
            max=1.0,
            default=0.0
        ))
    
    return ShaderSpec(name=name, uniforms=uniforms)


def load_shader_program(shader_path: str, name: Optional[str] = None, 
                       glsl_version: Optional[str] = None,
                       vao: Optional[int] = None) -> ShaderProgram:
    """
    Load a shader file and create a ShaderProgram with auto-detected spec.
    
    Args:
        shader_path: Path to shader file
        name: Optional shader name (defaults to filename without extension)
        glsl_version: Optional GLSL version (auto-detected if None)
        vao: Optional VAO for compilation (required for core profile)
        
    Returns:
        Compiled ShaderProgram instance
    """
    path = Path(shader_path)
    if not path.exists():
        raise FileNotFoundError(f"Shader file not found: {path}")
    
    if name is None:
        name = path.stem
    
    # Read shader source
    with open(path, 'r') as f:
        fragment_source = f.read()
    
    # Create a minimal spec (uniforms will be auto-detected after compilation)
    # We'll create a default spec and then update it
    spec = ShaderSpec(name=name, uniforms=[])
    
    # Create and compile shader program
    shader_program = ShaderProgram(spec, fragment_source, glsl_version)
    shader_program.compile(vao=vao)
    
    # Now create proper spec from compiled program
    spec = create_shader_spec_from_program(shader_program, name)
    shader_program.spec = spec
    
    return shader_program


def create_default_shader_spec(name: str) -> ShaderSpec:
    """
    Create a default ShaderSpec with no custom uniforms.
    
    This is useful for shaders that only use standard Shadertoy uniforms.
    
    Args:
        name: Shader name
        
    Returns:
        ShaderSpec with no custom uniforms
    """
    return ShaderSpec(name=name, uniforms=[])