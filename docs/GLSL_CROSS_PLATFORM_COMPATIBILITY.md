# GLSL Cross-Platform Compatibility Guide

## Current Platform Support

| Platform | Hardware | OpenGL Version | GLSL Version | Status |
|----------|----------|----------------|--------------|--------|
| **macOS** | Metal 89.3 | 2.1 | #version 120 | ✅ Working |
| **Raspberry Pi 5** | VideoCore VII | ES 3.0 | #version 300 es | ✅ Working |

## Version Differences

### GLSL 1.20 (macOS)
- **Released**: 2006 with OpenGL 2.1
- **Attribute syntax**: `attribute`, `varying`
- **Fragment output**: `gl_FragColor` (built-in)
- **Texture function**: `texture2D()`
- **Precision**: Not required

### GLSL ES 3.00 (Raspberry Pi)
- **Released**: 2012 with OpenGL ES 3.0
- **Attribute syntax**: `in`, `out`
- **Fragment output**: Explicit `out vec4 fragColor;`
- **Texture function**: `texture()` (unified)
- **Precision**: Required (`precision mediump float;`)

## Current Polyfills (shader_compiler.py)

Your compiler currently implements these polyfills for **GLSL 1.20 only**:

### ✅ Implemented

#### 1. `texture()` → `texture2D()`
```glsl
#define texture texture2D
```
**Reason**: GLSL 1.20 uses separate functions (`texture2D`, `textureCube`), GLSL ES 3.00 uses unified `texture()`

#### 2. `tanh()` - Hyperbolic Tangent
```glsl
float tanh(float x) {
    float e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}
// + vec2, vec3, vec4 overloads
```
**Reason**: Added in GLSL 1.30, not available in 1.20

#### 3. `round()` - Round to Nearest Integer
```glsl
float round(float x) {
    return floor(x + 0.5);
}
// + vec2, vec3, vec4 overloads
```
**Reason**: Added in GLSL 1.30, not available in 1.20

## Missing Functions in GLSL 1.20

These functions are available in GLSL ES 3.00 but NOT in GLSL 1.20:

### ❌ Not Implemented (May Want to Add)

#### 1. `sinh()` - Hyperbolic Sine
**Added in**: GLSL 1.30
**Formula**:
```glsl
float sinh(float x) {
    return (exp(x) - exp(-x)) / 2.0;
}
```

#### 2. `cosh()` - Hyperbolic Cosine
**Added in**: GLSL 1.30
**Formula**:
```glsl
float cosh(float x) {
    return (exp(x) + exp(-x)) / 2.0;
}
```

#### 3. `asinh()` - Inverse Hyperbolic Sine
**Added in**: GLSL 1.30
**Formula**:
```glsl
float asinh(float x) {
    return log(x + sqrt(x * x + 1.0));
}
```

#### 4. `acosh()` - Inverse Hyperbolic Cosine
**Added in**: GLSL 1.30
**Formula**:
```glsl
float acosh(float x) {
    return log(x + sqrt(x * x - 1.0));
}
```

#### 5. `atanh()` - Inverse Hyperbolic Tangent
**Added in**: GLSL 1.30
**Formula**:
```glsl
float atanh(float x) {
    return 0.5 * log((1.0 + x) / (1.0 - x));
}
```

#### 6. `trunc()` - Truncate to Integer
**Added in**: GLSL 1.30
**Formula**:
```glsl
float trunc(float x) {
    return x >= 0.0 ? floor(x) : ceil(x);
}
```

#### 7. `roundEven()` - Round to Nearest Even Integer
**Added in**: GLSL 1.30
**Formula**:
```glsl
float roundEven(float x) {
    float r = round(x);
    // If exactly halfway between two integers, round to even
    if (abs(r - x) == 0.5) {
        return mod(r, 2.0) == 0.0 ? r : r + (x < 0.0 ? 1.0 : -1.0);
    }
    return r;
}
```

#### 8. `modf()` - Extract Integer and Fractional Parts
**Added in**: GLSL 1.30
**Formula**:
```glsl
float modf(float x, out float i) {
    i = floor(x);
    return x - i;
}
```

## Functions Available in Both Versions

These are safe to use without polyfills:

### Core Math
- `sin()`, `cos()`, `tan()` - Trigonometric functions
- `asin()`, `acos()`, `atan()` - Inverse trig functions
- `radians()`, `degrees()` - Angle conversion
- `exp()`, `log()`, `exp2()`, `log2()` - Exponential/logarithmic
- `pow()`, `sqrt()`, `inversesqrt()` - Power/root functions

### Common Functions
- `abs()`, `sign()` - Absolute value, sign extraction
- `floor()`, `ceil()`, `fract()` - Floor, ceiling, fractional part
- `mod()` - Modulo operation
- `min()`, `max()`, `clamp()` - Range operations
- `mix()` - Linear interpolation
- `step()`, `smoothstep()` - Step functions

### Geometric Functions
- `length()`, `distance()`, `dot()`, `cross()`
- `normalize()`, `faceforward()`, `reflect()`, `refract()`

### Vector/Matrix
- `matrixCompMult()` - Component-wise matrix multiply
- `lessThan()`, `greaterThan()`, `equal()`, `notEqual()` - Vector comparisons
- `any()`, `all()`, `not()` - Vector boolean operations

## Recommendations

### Current State (Minimal Polyfills)
Your current implementation is **good enough** for most use cases. You have:
- ✅ `tanh()` for smooth activation functions
- ✅ `round()` for pixel/coordinate operations
- ✅ `texture()` compatibility

### If You Want Complete Coverage

Add these polyfills to `shader_compiler.py` for comprehensive support:

```python
helper_functions = "" if is_modern else """
// Hyperbolic functions (GLSL 1.30+)
float sinh(float x) {
    return (exp(x) - exp(-x)) / 2.0;
}

float cosh(float x) {
    return (exp(x) + exp(-x)) / 2.0;
}

float tanh(float x) {
    float e = exp(2.0 * x);
    return (e - 1.0) / (e + 1.0);
}

// Rounding functions (GLSL 1.30+)
float round(float x) {
    return floor(x + 0.5);
}

float trunc(float x) {
    return x >= 0.0 ? floor(x) : ceil(x);
}

// Add vec2/vec3/vec4 overloads for each...
"""
```

### Priority Recommendations

**High Priority** (commonly used):
- ✅ `tanh()` - Already implemented
- ✅ `round()` - Already implemented
- ⚠️ `trunc()` - Common in pixel/coordinate math

**Medium Priority** (occasionally useful):
- ⚠️ `sinh()`, `cosh()` - Useful for advanced effects
- ⚠️ `modf()` - Integer/fraction extraction

**Low Priority** (rarely used):
- `asinh()`, `acosh()`, `atanh()` - Inverse hyperbolic
- `roundEven()` - Banking rounding (niche)

## Testing Your Shaders

### Check What Functions You're Using

```bash
# Find all math functions used in your shaders
grep -rh "sinh\|cosh\|tanh\|trunc\|roundEven\|modf" shaders/ | head -20
```

### Current Usage Analysis

Let me check what you're actually using:
