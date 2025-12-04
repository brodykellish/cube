"""
AI Integration Module - Claude Code powered shader generation.

Provides natural language interface for creating and refining shaders.
"""

from .shader_agent import ShaderAgent, ShaderGenerationResult
from . import shader_prompts

__all__ = ['ShaderAgent', 'ShaderGenerationResult', 'shader_prompts']
