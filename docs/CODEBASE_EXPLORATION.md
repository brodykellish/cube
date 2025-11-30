# Adafruit_Blinka_Raspberry_Pi5_Piomatter - Codebase Exploration Report

**Date:** November 24, 2025  
**Repository:** Adafruit_Blinka_Raspberry_Pi5_Piomatter  
**Status:** Active development with shader extensions (main branch)

---

## Executive Summary

This is a **Python library for driving HUB75 RGB LED matrix panels on Raspberry Pi 5** using the RP1 PIO (Programmable I/O) hardware. The codebase has been extended with **GPU-accelerated GLSL shader support** and includes cross-platform development tools for macOS, Linux, and Raspberry Pi.

The library provides a clean NumPy-based API while the underlying C++/C components handle low-level PIO communication and GPU rendering via OpenGL ES.

---

## Directory Structure

```
Adafruit_Blinka_Raspberry_Pi5_Piomatter/
├── src/                              # C++/C source code and Python modules
│   ├── pymain.cpp                    # Python pybind11 bindings
│   ├── protodemo.cpp                 # Demo/test C++ application
│   ├── protomatter.pio               # PIO assembly for HUB75 protocol
│   ├── piolib/                       # PIO abstraction layer
│   │   ├── pio_rp1.c                 # RP1-specific PIO implementation (Pi 5)
│   │   ├── piolib.c                  # Generic PIO interface
│   │   └── include/                  # Header files
│   ├── include/                      # C++ headers
│   └── piomatter/
│       ├── __init__.py               # Main module (imports C++ bindings)
│       ├── click.py                  # Click CLI decorator helpers
│       └── pixelmappers.py           # Custom pixel mapping utilities
│
├── examples/                         # 16 example scripts
│   ├── shader_demo.py                # GPU shader rendering on LED matrix
│   ├── simpletest.py                 # Basic colored rectangles (modified)
│   ├── play_gif.py                   # GIF animation playback
│   ├── fbmirror.py                   # Mirror Linux framebuffer
│   ├── virtualdisplay.py             # Run X applications on matrix
│   ├── rainbow_spiral.py             # Procedural animation
│   ├── quote_scroller.py             # Text scrolling
│   ├── triple_matrix_*.py            # Multi-panel examples (3 panels)
│   └── ... [13 more examples]
│
├── shaders/                          # 70+ GLSL shader files
│   ├── cartoon.glsl                  # Edge detection effect
│   ├── flame.glsl                    # Fire simulation
│   ├── clouds.glsl                   # Procedural clouds
│   ├── voronoi.glsl                  # Voronoi diagrams
│   ├── synthwave.glsl                # Retro grid animation
│   ├── accretion.glsl                # Black hole accretion disk
│   ├── mandle_brot.glsl              # Mandelbrot fractal
│   ├── dragon_torus.glsl             # 3D ray-marched torus
│   └── ... [62 more shaders + texture data files]
│
├── shader_renderer.py                # OpenGL ES shader rendering engine
├── shader_preview.py                 # Cross-platform macOS/Linux shader preview
├── test_shader_renderer.py           # Shader rendering validation tests
├── test_colors.py                    # Color space testing
│
├── Documentation
│   ├── CLAUDE.md                     # Comprehensive dev guide
│   ├── SHADER_README.md              # GPU shader support docs
│   ├── QUICKSTART_SHADERS.md         # Quick start guide
│   ├── LOCAL_DEVELOPMENT.md          # macOS development setup
│   └── README.md
│
├── setup.py                          # Python package setup with C++ extension
├── pyproject.toml                    # Project metadata
├── requirements.txt                  # Python dependencies
├── requirements-preview.txt          # macOS preview tool deps
└── env/                              # Python 3.12 virtual environment (included)
```

---

## Key Files Overview

### Core Python Modules

#### 1. `/src/piomatter/__init__.py`
- **Purpose:** Main module entry point
- **Exports:** C++ bindings via pybind11
  - `Colorspace` enum (RGB565, RGB888Packed)
  - `Geometry` class (display configuration)
  - `Orientation` enum (rotations)
  - `Pinout` enum (hardware configurations)
  - `PioMatter` class (main display driver)

#### 2. `/src/piomatter/click.py`
- **Purpose:** CLI helper decorators for consistent command-line interfaces
- **Key Feature:** `@standard_options` decorator adds matrix configuration flags to Click commands
- **Flags Added:**
  - `--width`, `--height` (matrix dimensions)
  - `--pinout` (hardware config)
  - `--num-planes` (color depth, 4-11)
  - `--num-address-lines` (scan rate, 4 or 5)
  - `--serpentine` / `--no-serpentine` (panel chaining)
  - `--orientation` (rotation)
  - `--num-lanes` (connector lanes)

#### 3. `/src/piomatter/pixelmappers.py`
- **Purpose:** Custom pixel mapping for non-standard panel arrangements
- **Use Case:** Multiple panels in custom layouts, non-serpentine chaining

### C++ Core Engine

#### 1. `/src/pymain.cpp`
- **Purpose:** pybind11 bindings exposing C++ classes to Python
- **Size:** ~13KB
- **Bindings:** Maps C++ classes to Python equivalents
- **Key Bindings:**
  - `PioMatter` class with `show()` method
  - `Geometry` configuration class
  - Enum types for colorspace, orientation, pinout

#### 2. `/src/piolib/pio_rp1.c`
- **Purpose:** RP1-specific PIO implementation for Raspberry Pi 5
- **Handles:** Direct PIO device communication via `/dev/pio0`
- **Protocol:** HUB75 LED matrix protocol timing and sequencing

#### 3. `/src/piolib/piolib.c`
- **Purpose:** Generic PIO abstraction layer
- **Interface:** Platform-independent PIO operations

#### 4. `/src/protomatter.pio`
- **Purpose:** PIO assembly program for HUB75 protocol
- **Format:** PIOASM (PIO assembly) for Raspberry Pi RP1

### GPU Shader Rendering (NEW)

#### 1. `/shader_renderer.py`
- **Purpose:** OpenGL ES shader rendering engine
- **Size:** ~19KB
- **Type:** Pure Python with ctypes bindings to system libraries
- **Key Classes:**
  - `ShaderRenderer`: Main rendering engine
  - Uses EGL/GBM for offscreen GPU rendering
  - No PyOpenGL dependency (direct ctypes to libEGL, libGLESv2, libgbm)
- **Capabilities:**
  - Compiles GLSL fragment shaders (Shadertoy format)
  - Renders to numpy arrays (H×W×3, RGB, uint8)
  - Supports iTime, iResolution, iFrame uniforms
  - ~30-60 FPS on 64×64 displays

#### 2. `/shader_preview.py`
- **Purpose:** Cross-platform shader development tool
- **Size:** ~11KB
- **Platforms:** macOS, Linux, Windows
- **Dependencies:** pygame, PyOpenGL, numpy
- **Features:**
  - Preview shaders at LED matrix resolution
  - Configurable scaling (8x is default for 512×512 window)
  - Interactive controls: ESC/Q (quit), SPACE (pause), R (restart)
  - Uses desktop OpenGL (not ES) for compatibility

#### 3. `/examples/shader_demo.py`
- **Purpose:** Full integration example - renders shaders on actual LED matrix
- **Integration:** Combines ShaderRenderer + PioMatter
- **CLI Options:**
  - `--shader` (required): Path to GLSL shader file
  - All standard PioMatter options (width, height, pinout, etc.)
  - `--fps`: Target frame rate
  - `--show-fps`: Display FPS counter

#### 4. `/test_shader_renderer.py`
- **Purpose:** Validate shader rendering without LED hardware
- **Use Case:** Verify OpenGL setup and shader compilation
- **Output:** Performance metrics (FPS, frame time)

---

## Shader Library

**Location:** `/shaders/` (70 files total)

### Categories

**Simple & Fast:**
- cartoon.glsl - Edge detection on 3D shapes
- stars.glsl - Starfield
- lines.glsl - Geometric patterns
- drops.glsl - Falling water drops

**Medium Complexity:**
- flame.glsl - Fire simulation
- clouds.glsl - Procedural clouds (4 variants)
- water.glsl - Water ripples
- happy_jump.glsl - Bouncing shapes
- synthwave.glsl - Retro grid animation

**Complex & Beautiful:**
- voronoi.glsl - Voronoi diagrams with 3D effects
- mandle_brot.glsl - Mandelbrot fractal zoom
- dragon_torus.glsl - Ray-marched 3D torus
- accretion.glsl - Black hole accretion disk
- tentacles.glsl - Ray-marched tentacles
- glass.glsl - Glossy reflection effects

**With Texture Data:**
- accretion2.glsl + accretion2.channel0 (~87KB texture)
- corridor.glsl + channel0/channel1 (~2.4MB textures)
- glass.glsl + channel0/channel1 (~2MB textures)
- fluff.glsl + fluff.channel0 (~22KB texture)

---

## Documentation Files

### 1. `/CLAUDE.md` (17KB)
**Comprehensive developer guide**
- Library overview and features
- Installation (source and PyPI)
- Complete Python API reference
- Architecture explanation
- Usage patterns and examples
- Performance optimization tips
- Troubleshooting guide
- Integration with PIL, OpenCV, Matplotlib
- Extension guidelines
- Comparison with rpi-gpu-hub75-matrix

### 2. `/SHADER_README.md` (11KB)
**GPU shader support documentation**
- Overview of shader rendering system
- Requirements (system libraries)
- Quick start examples
- Command-line options
- Programmatic API usage
- Architecture & how it works
- Performance metrics
- Shader compatibility
- Troubleshooting
- Shader gallery with performance notes
- Future enhancements roadmap

### 3. `/QUICKSTART_SHADERS.md` (6KB)
**Fast-track shader guide**
- One-time setup instructions
- Test that rendering works (no hardware)
- Running shaders on LED matrix
- Try different shaders (examples)
- Common configurations
- Integration code
- Troubleshooting quick reference
- Recommended shaders by complexity

### 4. `/LOCAL_DEVELOPMENT.md` (8KB)
**macOS shader development guide**
- Setup on macOS with pygame & PyOpenGL
- Shader preview workflow
- Development cycle (Mac → Pi)
- Usage examples
- Shader compatibility notes (Desktop GL vs ES)
- Tips for low-resolution LED design
- Performance expectations
- Recommended shaders for LED matrices
- Troubleshooting
- File organization
- Sync script example

### 5. `/README.md` (2.5KB)
**Main repository README**
- Basic overview
- Key features
- Links to documentation

---

## Examples Directory Analysis

### GPU Shader Examples
- **shader_demo.py** (7.5KB) - Full LED matrix shader rendering with all CLI options

### Basic/Simple Examples
- **simpletest.py** (860B) - Static image display (MODIFIED: added n_addr_lines=5)
- **single_panel_simpletest.py** (1.2KB) - Single panel configuration
- **bouncing_square.py** (1.7KB) - Animated bouncing square

### Image/Animation Examples
- **play_gif.py** (1.1KB) - GIF animation playback
- **playframes.py** (1.1KB) - Frame-by-frame display
- **fbmirror.py** (2.5KB) - Linux framebuffer mirroring
- **fbmirror_scaled.py** (4.5KB) - Framebuffer with scaling

### Advanced Examples
- **virtualdisplay.py** (4KB) - Run X applications on matrix
- **xdisplay_mirror.py** (4KB) - X11 display mirroring
- **quote_scroller.py** (2.4KB) - Text scrolling
- **rainbow_spiral.py** (4.1KB) - Procedural animation

### Multi-Panel Examples
- **triple_matrix_active3_simpletest.py** - 3-panel configuration
- **triple_matrix_active3_play_gif.py** - 3-panel GIF playback
- **rainbow_spiral_active3.py** (4.1KB) - 3-panel animation

### Configuration Variants
- **simpletest_addre_bgr.py** - Address lines variant, BGR color order
- **rainbow_spiral_active3.py** - Active3 pinout variant

---

## Build System

### Setup Configuration (`setup.py`)
```
- Uses pybind11 for C++/Python bindings
- C++ Extension: "piomatter._piomatter"
- Source files:
  * src/pymain.cpp (main bindings)
  * src/piolib/piolib.c (PIO abstraction)
  * src/piolib/pio_rp1.c (RP1-specific)
- Include directories:
  * ./src/include
  * ./src/piolib/include
- C++ Standard: C++20
- Debug flags: -g3 -Og
```

### Dependencies

**Core Requirements** (`requirements.txt`):
- Adafruit-Blinka
- adafruit-circuitpython-pioasm
- click
- numpy
- pillow

**Preview Tool** (`requirements-preview.txt`):
- pygame
- PyOpenGL
- PyOpenGL_accelerate
- numpy

**System Libraries Needed:**
- libgles2-mesa-dev (OpenGL ES)
- libgbm-dev (Generic Buffer Management)
- libegl1-mesa-dev (EGL for display)
- python3-dev (Python headers for C++ extension)

---

## Architecture Diagrams

### Data Flow: Display Operation

```
Python Application (NumPy framebuffer)
        |
        v
PioMatter.show() [Python]
        |
        v
pybind11 C++ Bindings
        |
        v
C++ PioMatter class
        |
        v
PIO HAL (piolib.c, pio_rp1.c)
        |
        v
/dev/pio0 (kernel PIO interface)
        |
        v
RP1 Programmable I/O
        |
        v
HUB75 LED Matrix Panels
```

### Data Flow: Shader Rendering

```
GLSL Shader File
        |
        v
ShaderRenderer.load_shader()
        |
        v
OpenGL ES Shader Compilation
        |
        v
ShaderRenderer.render() [GPU]
        |
        v
GPU Renders to framebuffer
        |
        v
glReadPixels() → NumPy Array (H×W×3 RGB)
        |
        v
Copy to PioMatter framebuffer
        |
        v
PioMatter.show()
        |
        v
LED Matrix Display
```

### Development Workflow: macOS Preview

```
Shader File
        |
        +-- shader_preview.py (macOS) ──> Visual Feedback
        |
        +-- scp to Pi
        |
        v
shader_demo.py (Raspberry Pi 5) ──> LED Matrix
```

---

## Git Status & Recent Activity

### Current State
- **Branch:** main
- **Status:** 17 files modified (examples and new shader files)
- **Untracked Files:** 20+ new files (documentation, shaders, tools)

### Modified Examples (Code changes)
```
M examples/play_gif.py
M examples/playframes.py
M examples/quote_scroller.py
M examples/rainbow_spiral.py
M examples/rainbow_spiral_active3.py
M examples/simpletest.py
M examples/simpletest_addre_bgr.py
M examples/single_panel_simpletest.py
M examples/triple_matrix_active3_play_gif.py
M examples/triple_matrix_active3_simpletest.py
```

### New Files (Untracked)
```
?? CLAUDE.md
?? LOCAL_DEVELOPMENT.md
?? QUICKSTART_SHADERS.md
?? SHADER_README.md
?? shader_preview.py
?? shader_renderer.py
?? test_shader_renderer.py
?? test_colors.py
?? requirements-preview.txt
?? env/ (Python virtual environment)
?? examples/shader_demo.py
?? examples/bouncing_square.py
?? shaders/ (70 GLSL shader files)
```

### Recent Commits
```
27c2198 Merge pull request #62 from FoamyGuy/triple_matrix_gif
9206995 fix eof newline
bfb1e0e gif example for triple matrix
abd7f18 Merge pull request #55 from FoamyGuy/fix_active3_pinouts
```

---

## Cross-Platform Development Support

### macOS Development Setup
**File:** `LOCAL_DEVELOPMENT.md`

1. **System Dependencies:**
   - pygame (window rendering)
   - PyOpenGL (cross-platform OpenGL)
   - PyOpenGL_accelerate (GPU acceleration)

2. **Workflow:**
   - `shader_preview.py` on Mac for development
   - `scp` to copy to Pi
   - `shader_demo.py` on Pi for testing
   - Iterative develop → preview → deploy cycle

3. **Key Limitations on macOS:**
   - Desktop OpenGL (not ES) used for preview
   - Different shader precision requirements
   - Shaders work but may need minor adjustments
   - Color/brightness may differ from LED matrix

### Raspberry Pi 5 Support
- Direct `/dev/pio0` access for PIO operations
- OpenGL ES 3.1 via libGLESv2
- Offscreen rendering via EGL + GBM
- High refresh rates (200-400 Hz typical)

---

## Performance Characteristics

### Shader Rendering
**Hardware:** Raspberry Pi 5 GPU
- **64×64 Display @ 60 FPS:** 8-12ms GPU time, 55-80 FPS total
- **128×64 Display:** 100-200 Hz refresh (with shader)
- **Pixel Readback:** 1-2ms (glReadPixels)
- **Simple Shaders:** 30-60 FPS
- **Complex Shaders:** 20-40 FPS (ray marching)

### LED Matrix Display
- **HUB75 Protocol:** RP1 PIO hardware accelerated
- **Color Depth Configurations:** 4-11 bit-planes
- **Refresh Rate Range:** 200-400 Hz typical (depends on bit-planes)

---

## Known Features & Capabilities

### Supported
- Full OpenGL ES 3.1 support
- Shadertoy-compatible shader format
- Hardware-accelerated rendering (no CPU time)
- Zero-copy readback to NumPy
- All PioMatter configurations
- Multiple pinout configurations
- Panel chaining (serpentine and straight)
- Display rotation (4 orientations)
- Temporal dithering for smooth colors
- Custom pixel mapping

### Not Yet Supported
- Texture inputs (iChannel0, iChannel1)
- Multiple render passes (Buffer A, B, C)
- Mouse/keyboard input (iMouse)
- Audio input (iSampleRate)
- Interactive shader parameters

---

## Important Considerations

### Hardware Requirements
- **Raspberry Pi 5** (required for PIO and OpenGL ES)
- **HUB75 LED Matrix Panels** (addressable via PIO)
- **5V Power Supply** (2-4A per 64×32 panel at full brightness)

### System Setup
- Permissions: `/dev/pio0` and `/dev/dri/card0` access required
- udev rules needed for GPIO/DRM devices
- Real-time kernel recommended for smooth rendering

### Virtual Environment
- Pre-configured Python 3.12 venv included at `/env/`
- Contains dependencies for both runtime and development

---

## Summary of Additions

This codebase represents an **extension of the base Adafruit PioMatter library** with:

1. **GPU Shader Support** - Full OpenGL ES 3.1 integration with 70+ shaders
2. **Cross-Platform Development** - macOS shader preview tool for rapid iteration
3. **Comprehensive Documentation** - 4 specialized docs + CLAUDE.md guide
4. **Testing Infrastructure** - Shader validation and color space testing
5. **Python-First Design** - All shader integration via ctypes, no compilation needed

The library maintains backward compatibility while adding powerful GPU rendering capabilities, making it suitable for:
- Interactive LED installations
- Procedural animations
- Real-time visualization
- Shader art on LED matrices
- Python-based prototyping

---

**End of Report**
