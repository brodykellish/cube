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

    def __init__(self, action: Action, shader_path: str, node_class: str, trigger_mode: TriggerMode, priority: int = 100):
        """
        Initialize effect definition.

        Args:
            action: Action enum entry for this effect
            shader_path: Path to shader file
            node_class: Name of effect node class ("EffectNode", "FrameDifferencingEffectNode", or "ImageFlashEffectNode")
            trigger_mode: Trigger mode (toggle or momentary)
            priority: Priority level (lower values come first in chain, default: 100)
        """
        self.action = action
        self.shader_path = shader_path
        self.node_class = node_class
        self.trigger_mode = trigger_mode
        self.priority = priority

    def __repr__(self):
        return f"EffectDefinition(action={self.action.name}, shader={self.shader_path}, node_class={self.node_class}, trigger_mode={self.trigger_mode.value}, priority={self.priority})"


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
            priority = effect_data.get('priority', 100)

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
            # Dynamically gather all subclasses of EffectNode
            from cube.dag.effect_node import EffectNode

            valid_node_classes = [cls.__name__ for cls in EffectNode.__subclasses__()]
            valid_node_classes.append('EffectNode')  # Include base class if user wants it
            if node_class not in valid_node_classes:
                print(f"Warning: Invalid node_class '{node_class}' for effect {action_name}. Using 'EffectNode'.")
                node_class = 'EffectNode'

            # Validate priority is an integer
            try:
                priority = int(priority)
            except (ValueError, TypeError):
                print(f"Warning: Invalid priority '{priority}' for effect {action_name}. Using default 100.")
                priority = 100

            print(f"Loading effect: {action_name} with shader: {shader_path}, node_class: {node_class}, trigger_mode: {trigger_mode}, priority: {priority}")

            definition = EffectDefinition(
                action=action,
                shader_path=shader_path,  # Keep original path string for EffectManager
                node_class=node_class,
                trigger_mode=trigger_mode,
                priority=priority
            )
            definitions.append(definition)

        print(f"Loaded {len(definitions)} effect definitions from {config_path}")
        return definitions

    except Exception as e:
        print(f"Error: Failed to load effect config from {config_path}: {e}")
        import traceback
        traceback.print_exc()
        return []

