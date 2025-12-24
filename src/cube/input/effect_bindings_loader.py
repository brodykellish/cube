"""
Effect Bindings Loader - loads/saves effect bindings and presets.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple
import yaml
import tempfile
import shutil

from cube.input.actions import Action


class EffectBinding:
    """Single effect binding definition."""

    def __init__(self, action: Action, inputs: List[Union[str, Tuple[str, ...]]]):
        """
        Initialize effect binding.

        Args:
            action: Action enum entry for this effect
            inputs: List of input strings or tuples (e.g., ["midi:note_36", "key:1"] or [("key:shift", "key:1")])
        """
        self.action = action
        self.inputs = inputs

    def __repr__(self):
        return f"EffectBinding(action={self.action.name}, inputs={self.inputs})"


def _normalize_input(input_val: Union[str, List, Tuple]) -> Union[str, Tuple[str, ...]]:
    """
    Normalize input to either string or tuple format.
    
    Args:
        input_val: Input as string, list, or tuple
        
    Returns:
        Normalized input as string or tuple
    """
    if isinstance(input_val, str):
        return input_val
    elif isinstance(input_val, (list, tuple)):
        if len(input_val) == 1:
            return str(input_val[0])
        else:
            return tuple(str(x) for x in input_val)
    else:
        return str(input_val)


def load_effect_bindings(config_path: Optional[Path] = None) -> tuple[Optional[str], List[EffectBinding]]:
    """
    Load active effect bindings from YAML file.

    Args:
        config_path: Path to config file (default: effect_bindings.yml in project root)

    Returns:
        Tuple of (preset_name or None, list of EffectBinding instances)
    """
    if config_path is None:
        # Look for config in project root
        config_path = Path(__file__).parent.parent.parent.parent / 'effect_bindings.yml'

    if not config_path.exists():
        return None, []

    try:
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        if not config_dict:
            return None, []

        preset_name = config_dict.get('preset_name')
        bindings_list = config_dict.get('bindings', [])

        bindings: List[EffectBinding] = []
        for binding_data in bindings_list:
            # Validate required fields
            if 'action' not in binding_data or 'inputs' not in binding_data:
                print(f"Warning: Skipping binding with missing required fields: {binding_data}")
                continue

            action_name = binding_data['action']
            inputs_data = binding_data['inputs']

            # Validate Action enum exists
            try:
                action = Action[action_name]
            except KeyError:
                print(f"Warning: Action '{action_name}' not found in Action enum. Skipping binding.")
                continue

            # Normalize inputs (handle both string and tuple formats)
            inputs = [_normalize_input(inp) for inp in inputs_data]

            binding = EffectBinding(action, inputs)
            bindings.append(binding)

        return preset_name, bindings

    except Exception as e:
        print(f"Error: Failed to load effect bindings from {config_path}: {e}")
        import traceback
        traceback.print_exc()
        return None, []


def save_effect_bindings(bindings: List[EffectBinding], preset_name: Optional[str] = None, config_path: Optional[Path] = None) -> bool:
    """
    Save effect bindings to YAML file.

    Args:
        bindings: List of EffectBinding instances
        preset_name: Optional preset name to store
        config_path: Path to config file (default: effect_bindings.yml in project root)

    Returns:
        True if successful, False otherwise
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent.parent / 'effect_bindings.yml'

    try:
        # Prepare data structure
        config_dict = {
            'preset_name': preset_name,
            'bindings': []
        }

        for binding in bindings:
            # Convert inputs to YAML-serializable format
            inputs_serializable = []
            for inp in binding.inputs:
                if isinstance(inp, tuple):
                    inputs_serializable.append(list(inp))
                else:
                    inputs_serializable.append(inp)

            config_dict['bindings'].append({
                'action': binding.action.name,
                'inputs': inputs_serializable
            })

        # Atomic write: write to temp file, then rename
        temp_path = config_path.with_suffix('.yml.tmp')
        with open(temp_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        
        # Atomic rename
        shutil.move(str(temp_path), str(config_path))
        
        return True

    except Exception as e:
        print(f"Error: Failed to save effect bindings to {config_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_preset(preset_name: str, presets_dir: Optional[Path] = None) -> List[EffectBinding]:
    """
    Load a preset from file.

    Args:
        preset_name: Name of preset (without .yml extension)
        presets_dir: Directory containing presets (default: effect_bindings/ in project root)

    Returns:
        List of EffectBinding instances
    """
    if presets_dir is None:
        presets_dir = Path(__file__).parent.parent.parent.parent / 'effect_bindings'

    preset_path = presets_dir / f"{preset_name}.yml"

    if not preset_path.exists():
        print(f"Warning: Preset file not found: {preset_path}")
        return []

    _, bindings = load_effect_bindings(preset_path)
    return bindings


def save_preset(bindings: List[EffectBinding], preset_name: str, presets_dir: Optional[Path] = None) -> bool:
    """
    Save bindings as a preset.

    Args:
        bindings: List of EffectBinding instances
        preset_name: Name of preset (without .yml extension)
        presets_dir: Directory containing presets (default: effect_bindings/ in project root)

    Returns:
        True if successful, False otherwise
    """
    if presets_dir is None:
        presets_dir = Path(__file__).parent.parent.parent.parent / 'effect_bindings'

    # Ensure directory exists
    presets_dir.mkdir(parents=True, exist_ok=True)

    preset_path = presets_dir / f"{preset_name}.yml"
    return save_effect_bindings(bindings, preset_name=None, config_path=preset_path)


def list_presets(presets_dir: Optional[Path] = None) -> List[str]:
    """
    List all available presets.

    Args:
        presets_dir: Directory containing presets (default: effect_bindings/ in project root)

    Returns:
        List of preset names (without .yml extension)
    """
    if presets_dir is None:
        presets_dir = Path(__file__).parent.parent.parent.parent / 'effect_bindings'

    if not presets_dir.exists():
        return []

    presets = []
    for preset_file in presets_dir.glob('*.yml'):
        presets.append(preset_file.stem)

    return sorted(presets)


def delete_preset(preset_name: str, presets_dir: Optional[Path] = None) -> bool:
    """
    Delete a preset file.

    Args:
        preset_name: Name of preset (without .yml extension)
        presets_dir: Directory containing presets (default: effect_bindings/ in project root)

    Returns:
        True if successful, False otherwise
    """
    if presets_dir is None:
        presets_dir = Path(__file__).parent.parent.parent.parent / 'effect_bindings'

    preset_path = presets_dir / f"{preset_name}.yml"

    if not preset_path.exists():
        print(f"Warning: Preset file not found: {preset_path}")
        return False

    try:
        preset_path.unlink()
        return True
    except Exception as e:
        print(f"Error: Failed to delete preset {preset_name}: {e}")
        return False

