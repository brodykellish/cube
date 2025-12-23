"""
Effect Configuration Loader - loads YAML config for effect definitions.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml

from cube.input.actions import Action
from cube.render.effect_manager import TriggerMode


class EffectDefinition:
    """Single effect definition from config."""

    def __init__(self, action: Action, shader_path: str, node_class: str, trigger_mode: TriggerMode):
        """
        Initialize effect definition.

        Args:
            action: Action enum entry for this effect
            shader_path: Path to shader file
            node_class: Name of effect node class ("EffectNode", "FrameDifferencingEffectNode", or "ImageFlashEffectNode")
            trigger_mode: Trigger mode (toggle or momentary)
        """
        self.action = action
        self.shader_path = shader_path
        self.node_class = node_class
        self.trigger_mode = trigger_mode

    def __repr__(self):
        return f"EffectDefinition(action={self.action.name}, shader={self.shader_path}, node_class={self.node_class}, trigger_mode={self.trigger_mode.value})"


def load_effect_config(config_path: Optional[Path] = None) -> List[EffectDefinition]:
    """
    Load effect configuration from YAML file.

    Args:
        config_path: Path to config file (default: effects_config.yml in project root)

    Returns:
        List of EffectDefinition instances, or empty list if config doesn't exist or is invalid
    """
    if config_path is None:
        # Look for config in project root
        config_path = Path(__file__).parent.parent.parent.parent / 'effects_config.yml'

    if not config_path.exists():
        print(f"Warning: Effect config file not found at {config_path}")
        return []

    try:
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        if not config_dict or 'effects' not in config_dict:
            print(f"Warning: Invalid effect config format in {config_path}")
            return []

        definitions: List[EffectDefinition] = []
        effects_list = config_dict['effects']

        for effect_data in effects_list:
            # Validate required fields
            if 'action' not in effect_data or 'shader' not in effect_data:
                print(f"Warning: Skipping effect with missing required fields: {effect_data}")
                continue

            action_name = effect_data['action']
            shader_path = effect_data['shader']
            node_class = effect_data.get('node_class', 'EffectNode')
            trigger_mode_str = effect_data.get('trigger_mode', 'toggle')

            # Validate Action enum exists
            try:
                action = Action[action_name]
            except KeyError:
                print(f"Warning: Action '{action_name}' not found in Action enum. Skipping effect.")
                continue

            # Validate shader file exists
            shader_path_obj = Path(shader_path)
            if not shader_path_obj.is_absolute():
                # Relative path - resolve from project root
                project_root = Path(__file__).parent.parent.parent.parent
                shader_path_obj = project_root / shader_path

            if not shader_path_obj.exists():
                print(f"Warning: Shader file not found: {shader_path_obj}. Skipping effect.")
                continue

            # Validate trigger mode
            try:
                trigger_mode = TriggerMode(trigger_mode_str)
            except ValueError:
                print(f"Warning: Invalid trigger_mode '{trigger_mode_str}' for effect {action_name}. Using 'toggle'.")
                trigger_mode = TriggerMode.TOGGLE

            # Validate node class name
            valid_node_classes = ['EffectNode', 'FrameDifferencingEffectNode', 'ImageFlashEffectNode']
            if node_class not in valid_node_classes:
                print(f"Warning: Invalid node_class '{node_class}' for effect {action_name}. Using 'EffectNode'.")
                node_class = 'EffectNode'

            definition = EffectDefinition(
                action=action,
                shader_path=shader_path,  # Keep original path string for EffectManager
                node_class=node_class,
                trigger_mode=trigger_mode
            )
            definitions.append(definition)

        print(f"Loaded {len(definitions)} effect definitions from {config_path}")
        return definitions

    except Exception as e:
        print(f"Error: Failed to load effect config from {config_path}: {e}")
        import traceback
        traceback.print_exc()
        return []

