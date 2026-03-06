"""
Effect Registry Service.

Provides unified access to effect definitions, metadata, and bindings.
Combines effects_config.yml and effect_bindings.yml into a single interface.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
import yaml

from cube.input.actions import Action


@dataclass
class EffectInfo:
    """Complete information about an effect."""
    action: Action
    action_name: str
    shader_path: str
    node_class: str
    trigger_mode: str
    keybindings: List[List[str]]  # List of key combinations
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['action'] = self.action.name
        return d


class EffectRegistry:
    """
    Registry of all available effects with metadata and bindings.

    Provides single source of truth for:
    - Effect definitions (from effects_config.yml)
    - Keyboard bindings (from effect_bindings.yml)
    - Runtime effect state (active/inactive)

    Essential for quick effect discovery and toggling during live performance.
    """

    def __init__(
        self,
        effects_config_path: Path = None,
        bindings_config_path: Path = None,
        effect_manager=None
    ):
        """
        Initialize effect registry.

        Args:
            effects_config_path: Path to effects_config.yml
            bindings_config_path: Path to effect_bindings.yml
            effect_manager: Optional EffectManager for tracking active effects
        """
        if effects_config_path is None:
            effects_config_path = Path.cwd() / 'effects_config.yml'

        if bindings_config_path is None:
            bindings_config_path = Path.cwd() / 'effect_bindings.yml'

        self.effects_config_path = Path(effects_config_path)
        self.bindings_config_path = Path(bindings_config_path)
        self.effect_manager = effect_manager

        # Load configurations
        self._effects_by_action: Dict[Action, EffectInfo] = {}
        self._load_effects()
        self._load_bindings()

    def get_all_effects(self) -> List[EffectInfo]:
        """
        Get all available effects with current state.

        Returns:
            List of EffectInfo objects sorted by action name
        """
        effects = list(self._effects_by_action.values())

        # Update active state from effect manager
        if self.effect_manager:
            active_effects = set(self.effect_manager.get_active_effects())
            for effect in effects:
                effect.is_active = effect.action in active_effects

        effects.sort(key=lambda e: e.action_name)
        return effects

    def get_effect(self, action: Action) -> Optional[EffectInfo]:
        """
        Get effect info for a specific action.

        Args:
            action: Action enum value

        Returns:
            EffectInfo or None if not found
        """
        effect = self._effects_by_action.get(action)

        # Update active state
        if effect and self.effect_manager:
            effect.is_active = self.effect_manager.is_effect_active(action)

        return effect

    def get_effect_by_name(self, action_name: str) -> Optional[EffectInfo]:
        """
        Get effect info by action name string.

        Args:
            action_name: String name of action (e.g., "TOGGLE_GLITCH")

        Returns:
            EffectInfo or None if not found
        """
        try:
            action = Action[action_name]
            return self.get_effect(action)
        except KeyError:
            return None

    def get_active_effects(self) -> List[EffectInfo]:
        """
        Get list of currently active effects.

        Returns:
            List of active EffectInfo objects
        """
        if not self.effect_manager:
            return []

        active_actions = self.effect_manager.get_active_effects()
        active_effects = []

        for action in active_actions:
            effect = self._effects_by_action.get(action)
            if effect:
                effect.is_active = True
                active_effects.append(effect)

        return active_effects

    def is_effect_active(self, action: Action) -> bool:
        """
        Check if an effect is currently active.

        Args:
            action: Action to check

        Returns:
            True if effect is active, False otherwise
        """
        if not self.effect_manager:
            return False

        return self.effect_manager.is_effect_active(action)

    def get_effects_by_keybinding(self, keys: List[str]) -> List[EffectInfo]:
        """
        Find effects that match a key combination.

        Args:
            keys: List of key names (e.g., ['shift', '1'])

        Returns:
            List of matching EffectInfo objects
        """
        matching_effects = []

        for effect in self._effects_by_action.values():
            for binding in effect.keybindings:
                if set(binding) == set(keys):
                    matching_effects.append(effect)
                    break

        return matching_effects

    def search_effects(self, query: str) -> List[EffectInfo]:
        """
        Search effects by name or shader path.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching EffectInfo objects
        """
        query_lower = query.lower()
        matching_effects = []

        for effect in self._effects_by_action.values():
            if (query_lower in effect.action_name.lower() or
                query_lower in effect.shader_path.lower()):
                matching_effects.append(effect)

        return matching_effects

    def get_effect_categories(self) -> Dict[str, List[EffectInfo]]:
        """
        Group effects by category based on shader directory.

        Returns:
            Dictionary mapping category name to list of effects
        """
        categories = {}

        for effect in self._effects_by_action.values():
            # Extract category from shader path (e.g., "shaders/effects/glitch.glsl" → "effects")
            path_parts = Path(effect.shader_path).parts
            category = path_parts[1] if len(path_parts) > 1 else "other"

            if category not in categories:
                categories[category] = []

            categories[category].append(effect)

        # Sort effects within each category
        for category_effects in categories.values():
            category_effects.sort(key=lambda e: e.action_name)

        return categories

    def reload(self):
        """Reload effect configurations from disk."""
        self._effects_by_action.clear()
        self._load_effects()
        self._load_bindings()

    def _load_effects(self):
        """Load effect definitions from effects_config.yml."""
        if not self.effects_config_path.exists():
            print(f"[EffectRegistry] Warning: Effects config not found: {self.effects_config_path}")
            return

        try:
            with open(self.effects_config_path, 'r') as f:
                config = yaml.safe_load(f)

            for effect_data in config.get('effects', []):
                action_name = effect_data['action']

                try:
                    action = Action[action_name]

                    effect_info = EffectInfo(
                        action=action,
                        action_name=action_name,
                        shader_path=effect_data['shader'],
                        node_class=effect_data.get('node_class', 'EffectNode'),
                        trigger_mode=effect_data.get('trigger_mode', 'toggle'),
                        keybindings=[],  # Will be populated by _load_bindings
                        is_active=False
                    )

                    self._effects_by_action[action] = effect_info

                except KeyError:
                    print(f"[EffectRegistry] Warning: Unknown action: {action_name}")

            print(f"[EffectRegistry] Loaded {len(self._effects_by_action)} effects")

        except Exception as e:
            print(f"[EffectRegistry] Error loading effects config: {e}")

    def _load_bindings(self):
        """Load keyboard bindings from effect_bindings.yml and merge with effects."""
        if not self.bindings_config_path.exists():
            print(f"[EffectRegistry] Warning: Bindings config not found: {self.bindings_config_path}")
            return

        try:
            with open(self.bindings_config_path, 'r') as f:
                config = yaml.safe_load(f)

            bindings_data = config.get('bindings', [])

            for binding in bindings_data:
                action_name = binding['action']

                try:
                    action = Action[action_name]

                    if action in self._effects_by_action:
                        # Parse input bindings
                        keybindings = []
                        for input_combo in binding.get('inputs', []):
                            if isinstance(input_combo, list):
                                # Multiple keys (e.g., [['key:shift'], ['key:1']])
                                keys = [item.replace('key:', '') for item in input_combo if isinstance(item, dict)]
                                if not keys:
                                    # Simple list format: ['key:shift', 'key:1']
                                    keys = [item.replace('key:', '') for item in input_combo]
                                keybindings.append(keys)
                            elif isinstance(input_combo, dict):
                                # Single key dict format (legacy)
                                for key_type, key_val in input_combo.items():
                                    if key_type == 'key':
                                        keybindings.append([str(key_val)])
                            else:
                                # Single key string
                                key = str(input_combo).replace('key:', '')
                                keybindings.append([key])

                        self._effects_by_action[action].keybindings = keybindings

                except KeyError:
                    # Action not in effects_config, skip
                    pass

            print(f"[EffectRegistry] Loaded bindings for {len(self._effects_by_action)} effects")

        except Exception as e:
            print(f"[EffectRegistry] Error loading bindings config: {e}")

    def __repr__(self) -> str:
        return f"EffectRegistry({len(self._effects_by_action)} effects)"
