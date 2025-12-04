# AI Shader Generation System

## Overview

The AI shader generation system integrates Claude (via Anthropic API) directly into the cube control system, allowing users to create custom GLSL shaders through natural language prompts.

## Architecture

### Components

1. **ShaderAgent** (`src/cube/ai/shader_agent.py`)
   - Core AI integration using Anthropic Python SDK
   - Handles shader generation requests
   - Maintains conversation history for iterative refinement
   - Extracts and validates GLSL code from Claude's responses

2. **PromptMenuState** (`src/cube/menu/prompt_menu.py`)
   - Interactive UI for natural language input
   - Text box with scrolling conversation history
   - Real-time shader generation feedback
   - Automatic shader launching after generation

3. **Generated Shaders Directory** (`shaders/generated/`)
   - Write-only directory for AI-generated shaders
   - Automatically created if doesn't exist
   - Shaders named based on user prompts

## Setup

### 1. Install Dependencies

```bash
pip install anthropic
```

### 2. Configure API Key

```bash
export ANTHROPIC_API_KEY='your-anthropic-api-key-here'
```

### 3. Verify Installation

```bash
python3 test_shader_agent.py
```

## Usage

### From the Menu System

1. Launch cube control: `python3 cube_control.py`
2. Navigate to "AI Generate" option in main menu
3. Type your shader description
4. Press ENTER to generate
5. Shader automatically displays when ready
6. Press ESC to return to prompt for refinements

### Programmatically

```python
from pathlib import Path
from cube.ai import ShaderAgent

# Initialize agent
shaders_dir = Path('shaders/generated')
agent = ShaderAgent(shaders_dir)

# Generate shader
result = agent.generate_shader(
    "Create a rotating torus with rainbow colors"
)

if result.success:
    print(f"Generated: {result.shader_path}")
```

## API Key Setup

Make sure to set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY='your-key-here'
```
