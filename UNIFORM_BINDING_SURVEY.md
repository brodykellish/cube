# Uniform Binding Survey

This document surveys all places where uniforms are bound/set in the rendering pipeline.

## Uniform Collection (DAGRenderer)

**Location**: `src/cube/render/dag_renderer.py::_update_uniforms()`

This is the central place where all uniforms are collected from various sources:

1. **Camera uniforms** (from `camera_source`)
   - Updates: `camera_source.update(dt)`
   - Gets: `camera_source.get_uniforms()` → adds to uniforms dict

2. **Parameter uniforms** (from `param_source`)
   - Updates: `param_source.update(dt)`
   - Gets: `param_source.get_uniforms()` → adds to uniforms dict

3. **Additional uniform sources** (from `uniform_sources` list)
   - Updates: `source.update(dt)` for each source
   - Gets: `source.get_uniforms()` → adds to uniforms dict

4. **Standard uniforms** (set directly):
   - `iTime` = elapsed time
   - `iFrame` = frame count
   - `iTimeDelta` = 0.016 (fixed)
   - `iMouse` = from `mouse_source.get_uniforms()`
   - `iDebugAxes` = from settings

**Output**: Returns a dictionary of all uniforms

## Uniform Distribution (DAGRenderer.render)

**Location**: `src/cube/render/dag_renderer.py::render()`

1. **Line 159**: Calls `_update_uniforms(elapsed)` to get base uniforms dict
2. **Line 177-178**: For each node, creates `node_uniforms` copy and adds `iResolution`
3. **Line 182**: Passes `node_uniforms` to `EffectNode.render()`
4. **Line 185**: Passes `node_uniforms` to `SourceNode.render()`
5. **Line 188**: Passes `node_uniforms` to `VideoSourceNode.render()`
6. **Line 201**: For cube faces, re-updates uniforms and re-renders with updated camera

## Uniform Binding in Nodes

### SourceNode

**Location**: `src/cube/dag/source_node.py::render()`

1. **Line 108**: `self.shader.use()` - activates shader program
2. **Line 120-122**: Iterates through `uniforms` dict and calls `self.shader.set_uniform(name, value)` for each

### EffectNode

**Location**: `src/cube/dag/effect_node.py::render()`

1. **Line 78**: `self.shader.use()` - activates shader program
2. **Line 80-82**: Iterates through `uniforms` dict and calls `self.shader.set_uniform(name, value)` for each

### VideoSourceNode

**Location**: `src/cube/dag/video_source_node.py::render()`

- Does NOT bind uniforms (no shader program)

## Low-Level Uniform Setting (ShaderProgram)

**Location**: `src/cube/shader/program.py::set_uniform()`

This is the actual OpenGL call site:

1. **Line 152**: Gets uniform location from cache: `self.uniform_locations.get(name)`
2. **Line 156-157**: If int/bool → `glUniform1i(location, int(value))`
3. **Line 158-159**: If float → `glUniform1f(location, float(value))`
4. **Line 160-172**: If tuple/list:
   - Length 2 → `glUniform2f(...)`
   - Length 3 → `glUniform3f(...)`
   - Length 4 → `glUniform4f(...)`

## Texture Uniform Binding

**Location**: `src/cube/shader/program.py::set_texture()`

1. **Line 186**: `glActiveTexture(GL_TEXTURE0 + texture_unit)`
2. **Line 187**: `glBindTexture(GL_TEXTURE_2D, texture_id)`
3. **Line 188**: `glUniform1i(location, texture_unit)` - sets sampler uniform

**Called from**:
- `SourceNode.render()`: Binds shader textures (iChannel0-3) from `_shader_textures`
- `EffectNode.render()`: Binds input texture to iChannel0, additional textures to other channels

## Uniform Sources

Uniforms come from these sources (via `get_uniforms()`):

1. **CameraUniformSource**: `iCameraPos`, `iCameraDir`, `iCameraUp`, etc.
2. **ParameterUniformSource**: `iParam0` through `iParam7`
3. **MouseUniformSource**: `iMouse` (x, y, click, drag)
4. **Additional sources** (MIDI, audio, etc.): Various custom uniforms

## Summary

**Uniform Flow**:
1. `DAGRenderer._update_uniforms()` → collects all uniforms from sources
2. `DAGRenderer.render()` → distributes uniforms to each node (with per-node `iResolution`)
3. `Node.render()` → calls `shader.set_uniform()` for each uniform
4. `ShaderProgram.set_uniform()` → calls OpenGL `glUniform*` functions

**Key Points**:
- Uniforms are collected once per frame in `_update_uniforms()`
- Each node gets a copy of uniforms with its own `iResolution` added
- Nodes iterate through uniforms dict and call `shader.set_uniform()` for each
- Actual OpenGL binding happens in `ShaderProgram.set_uniform()`


