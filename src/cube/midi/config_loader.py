"""
MIDI Configuration Loader - loads YAML config for USB MIDI mapping.
"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml


class MIDIMapping:
    """Single MIDI CC to parameter mapping."""

    def __init__(self, midi_cc: int, target: str, min_val: int = 0, max_val: int = 127):
        """
        Initialize MIDI mapping.

        Args:
            midi_cc: MIDI CC number from controller (0-127)
            target: Target parameter name ('param0', 'param1', 'param2', 'param3')
            min_val: Minimum MIDI value to accept
            max_val: Maximum MIDI value to accept
        """
        self.midi_cc = midi_cc
        self.target = target
        self.min_val = min_val
        self.max_val = max_val

        # Map target name to CC number
        target_map = {
            'param0': 0,
            'param1': 1,
            'param2': 2,
            'param3': 3,
        }

        if target not in target_map:
            raise ValueError(f"Invalid target '{target}'. Must be param0-3.")

        self.target_cc = target_map[target]

    def __repr__(self):
        return f"MIDIMapping(cc{self.midi_cc} -> {self.target})"


class MIDIConfig:
    """MIDI controller configuration."""

    def __init__(self, device_name: str, mappings: List[MIDIMapping]):
        """
        Initialize MIDI config.

        Args:
            device_name: MIDI device name to connect to (or "auto")
            mappings: List of MIDI CC mappings
        """
        self.device_name = device_name
        self.mappings = mappings

    def get_mapping_for_cc(self, midi_cc: int) -> Optional[MIDIMapping]:
        """
        Get mapping for a specific MIDI CC number.

        Args:
            midi_cc: MIDI CC number

        Returns:
            MIDIMapping if found, None otherwise
        """
        for mapping in self.mappings:
            if mapping.midi_cc == midi_cc:
                return mapping
        return None

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'MIDIConfig':
        """
        Create MIDIConfig from dictionary (loaded from YAML).

        Args:
            config_dict: Configuration dictionary

        Returns:
            MIDIConfig instance
        """
        device_name = config_dict.get('device_name', 'auto')
        mappings_data = config_dict.get('mappings', [])

        mappings = []
        for m in mappings_data:
            mapping = MIDIMapping(
                midi_cc=m['midi_cc'],
                target=m['target'],
                min_val=m.get('min', 0),
                max_val=m.get('max', 127)
            )
            mappings.append(mapping)

        return cls(device_name, mappings)


def load_midi_config(config_path: Optional[Path] = None) -> Optional[MIDIConfig]:
    """
    Load MIDI configuration from YAML file.

    Args:
        config_path: Path to config file (default: midi_config.yml in project root)

    Returns:
        MIDIConfig instance, or None if config doesn't exist or is invalid
    """
    if config_path is None:
        # Look for config in project root
        config_path = Path(__file__).parent.parent.parent.parent / 'midi_config.yml'

    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        return MIDIConfig.from_dict(config_dict)

    except Exception as e:
        print(f"Warning: Failed to load MIDI config from {config_path}: {e}")
        return None
