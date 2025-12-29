"""
Binding system with modal overlay stack support.

Maps physical inputs (keys, MIDI) to semantic actions/axes.
Supports temporary overlays for modes like envelope editor.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Union, Callable, Optional
from pathlib import Path
from .actions import Action, Axis, InputContext, ActionState
from .input_source import InputState


# Helper transform functions for common patterns
def passthrough(scale: float = 1.0) -> Callable[[float, float], float]:
    """
    Direct mapping with optional scale.

    Args:
        scale: Multiplier for input value

    Returns:
        Transform function: (cur, input_val) -> input_val * scale
    """
    return lambda cur, input_val: input_val * scale


def inverted(scale: float = 1.0) -> Callable[[float, float], float]:
    """
    Inverted mapping with optional scale.

    Args:
        scale: Multiplier for input value

    Returns:
        Transform function: (cur, input_val) -> -input_val * scale
    """
    return lambda cur, input_val: -input_val * scale


def increment(rate: float = 0.01) -> Callable[[float, float], float]:
    """
    Continuous increment while held (clamped to 0-1).

    Args:
        rate: Increment per input unit

    Returns:
        Transform function: (cur, input_val) -> clamp(cur + input_val * rate, 0, 1)
    """
    return lambda cur, input_val: min(1.0, cur + input_val * rate)


def decrement(rate: float = 0.01) -> Callable[[float, float], float]:
    """
    Continuous decrement while held (clamped to 0-1).

    Args:
        rate: Decrement per input unit

    Returns:
        Transform function: (cur, input_val) -> clamp(cur - input_val * rate, 0, 1)
    """
    return lambda cur, input_val: max(0.0, cur - input_val * rate)


@dataclass
class Binding:
    """Maps a raw input to an action/axis"""
    target: Union[Action, Axis]
    transform: Optional[Callable[[float, float], float]] = None
    # transform(cur, input_val) -> new_value
    # cur: current cumulative axis value for this frame
    # input_val: input from source (0.0-1.0 for MIDI, 1.0 for held keys)
    # If None, defaults to direct pass-through (new_value = input_val)


@dataclass
class BindingOverlay:
    """Temporary binding overlay for modal input (envelope mode, etc.)"""
    name: str
    # {raw_input: target} - can be string or tuple
    bindings: Dict[Union[str, tuple], Union[Action, Axis]]
    context: InputContext


class BindingMap:
    """
    Manages input bindings with overlay stack.

    Base bindings + stack of overlays (overlays checked first).
    Supports live remapping and save/load.
    """

    def __init__(self):
        # Base bindings: {context: {raw_input: [Binding]}}
        self.base: Dict[InputContext, Dict[tuple[str], List[Binding]]] = {}

        # Reverse index: {context: {target: [raw_input]}}
        self.reverse: Dict[InputContext,
                           Dict[Union[Action, Axis], tuple[str]]] = {}

        # Track previous CC values for direction detection (e.g., CC 114 navigation)
        self._last_cc_values: Dict[str, float] = {}

        # File watching for effect bindings
        self._effect_bindings_config_path: Optional[Path] = None
        self._last_config_mtime: Optional[float] = None
        self._config_check_accumulator: float = 0.0
        # Track which actions are effect bindings (loaded from config file)
        self._effect_binding_actions: Set[Action] = set()

        # Load defaults
        self._load_defaults()
        # Load effect bindings (overrides defaults)
        self._load_effect_bindings()

    def add_binding(self, context: InputContext,
                    target: Union[Action, Axis],
                    raw_input: tuple[str],
                    transform: Optional[Callable[[float, float], float]] = None):
        """
        Add a binding to the base bindings.

        Args:
            context: Input context
            target: Action or Axis to bind to
            raw_input: Tuple of keys (e.g., ('key:shift', 'key:w'))
            transform: Transform function (cur, input_val) -> new_value
                      If None, defaults to pass-through (new_value = input_val)
        """
        # Initialize context if needed
        if context not in self.base:
            self.base[context] = {}
        if context not in self.reverse:
            self.reverse[context] = {}

        # Add to forward index
        if raw_input not in self.base[context]:
            self.base[context][raw_input] = []

        binding = Binding(target, transform)
        self.base[context][raw_input].append(binding)

        # Add to reverse index
        if target not in self.reverse[context]:
            self.reverse[context][target] = []
        if raw_input not in self.reverse[context][target]:
            self.reverse[context][target].append(raw_input)

    def remove_binding(self, context: InputContext, target: Union[Action, Axis],
                       raw_input: tuple[str]):
        """Remove a specific binding"""
        # Remove from forward index
        if context in self.base and raw_input in self.base[context]:
            self.base[context][raw_input] = [
                b for b in self.base[context][raw_input]
                if b.target != target
            ]
            # Clean up empty lists
            if not self.base[context][raw_input]:
                del self.base[context][raw_input]

        # Remove from reverse index
        if context in self.reverse and target in self.reverse[context]:
            if raw_input in self.reverse[context][target]:
                self.reverse[context][target].remove(raw_input)
            # Clean up empty lists
            if not self.reverse[context][target]:
                del self.reverse[context][target]

    def get_raw_inputs(self, target: Union[Action, Axis],
                       context: InputContext) -> List[str]:
        """Get all raw inputs bound to a target (for UI display)"""
        return self.reverse.get(context, {}).get(target, []).copy()

    def resolve_actions_with_overlays(self, raw_states: List[InputState],
                                      context: InputContext,
                                      overlays: List[BindingOverlay]):
        """
        Resolve raw inputs to actions (overlays checked first).

        Args:
            raw_states: Input states from all sources
            context: Current input context
            overlays: Stack of binding overlays (top = most recent)

        Returns:
            {Action: ActionState} for all active actions
        """
        # Collect all raw discrete inputs
        all_pressed = set()
        all_held = set()
        all_released = set()

        for state in raw_states:
            all_pressed.update(state.pressed)
            all_held.update(state.held)
            all_released.update(state.released)

        # Build expanded key sets with modifiers applied
        # When shift is held, we can match bindings like ('key:shift', 'key:w')
        # by checking if both 'key:shift' and 'key:w' are in the held set
        expanded_pressed = all_pressed.copy()
        expanded_held = all_held.copy()

        # No need to add tuples to sets - we'll check subset membership directly

        result = {}
        consumed = set()

        # Check overlays top-down (most recent first)
        for overlay in reversed(overlays):
            if overlay.context != context:
                continue

            for raw_input, target in overlay.bindings.items():
                if not isinstance(target, Action):
                    continue

                # Convert overlay binding to tuple if it's a string
                if isinstance(raw_input, str):
                    binding_keys = (raw_input,)
                else:
                    binding_keys = raw_input

                # Check if binding is a subset of current keys
                binding_set = set(binding_keys)
                if binding_set.issubset(expanded_held):
                    # Check if it's pressed (last key in tuple was pressed)
                    if binding_keys:
                        last_key = binding_keys[-1]
                        is_pressed = last_key in all_pressed
                    else:
                        is_pressed = False

                    if is_pressed:
                        result[target] = ActionState.PRESSED
                    else:
                        result[target] = ActionState.HELD

                    consumed.update(binding_keys)

        # Check base bindings (for unconsumed inputs)
        # Sort bindings by length (longer = more specific = check first)
        # This ensures modifier+key bindings are checked before single-key bindings
        base_bindings = list(self.base.get(context, {}).items())
        base_bindings.sort(key=lambda x: len(x[0]), reverse=True)

        for binding_keys, bindings in base_bindings:
            # Skip if any key in binding is already consumed
            if any(k in consumed for k in binding_keys):
                continue

            binding_set = set(binding_keys)

            # Check if binding is a subset of current keys
            if binding_set.issubset(expanded_held):
                # Check if it's pressed (last key in tuple was pressed)
                if binding_keys:
                    last_key = binding_keys[-1]
                    is_pressed = last_key in all_pressed
                else:
                    is_pressed = False

                for binding in bindings:
                    if isinstance(binding.target, Action):
                        if is_pressed:
                            result[binding.target] = ActionState.PRESSED
                        else:
                            result[binding.target] = ActionState.HELD

                        # Mark all keys in binding as consumed
                        consumed.update(binding_keys)

        return result

    def resolve_axes_with_overlays(self, raw_states: List[InputState],
                                   context: InputContext,
                                   overlays: List[BindingOverlay]) -> Dict[Axis, float]:
        """
        Resolve raw inputs to axes (overlays first, priority for conflicts).

        Args:
            raw_states: Input states from all sources
            context: Current input context
            overlays: Stack of binding overlays

        Returns:
            {Axis: float} for all active axes
        """
        # Collect all axes with source priority
        all_axes = {}  # {raw_input: (value, source_priority)}
        all_held = set()

        for state in raw_states:
            # Continuous axes from state.axes dict
            for raw_input, value in state.axes.items():
                if (raw_input not in all_axes or
                        state.source_priority > all_axes[raw_input][1]):
                    all_axes[raw_input] = (value, state.source_priority)

            # Track held keys for modifier matching
            all_held.update(state.held)

        # Check for shift modifier
        shift_held = 'key:shift' in all_held
        cc9_held = False

        # Check for CC 9 as modifier (equivalent to shift)
        for state in raw_states:
            if 'midi:cc_9' in state.axes:
                cc9_val = state.axes['midi:cc_9']
                cc9_held = cc9_val > 0.5
                break

        # Build expanded key sets with modifiers applied
        # When shift is held, we can match bindings like ('key:shift', 'key:w')
        # by checking if both 'key:shift' and 'key:w' are in the held set
        expanded_held = all_held.copy()

        result = {}
        consumed = set()

        # Check overlays top-down (overlays work in any context)
        for overlay in reversed(overlays):
            for raw_input, target in overlay.bindings.items():
                if not isinstance(target, Axis):
                    continue

                # Extract key from raw_input (handles string or tuple)
                key = None
                if isinstance(raw_input, str):
                    key = raw_input
                elif isinstance(raw_input, tuple) and len(raw_input) > 0:
                    # Single-key tuple: use the key
                    if len(raw_input) == 1:
                        key = raw_input[0]
                    # Multi-key tuple: check modifiers, use last key
                    elif set(raw_input[:-1]).issubset(expanded_held):
                        key = raw_input[-1]

                if key is None:
                    continue

                # Simple lookup: if key is in all_axes, use its value
                if key in all_axes:
                    value, _ = all_axes[key]
                    result[target] = value
                    consumed.add(key)
                # If key is held (discrete key), use 1.0
                elif key in expanded_held:
                    result[target] = 1.0
                    consumed.add(key)

        # Check base bindings (for unconsumed inputs)
        # Sort bindings by length (longer = more specific = check first)
        # This ensures modifier+key bindings are checked before single-key bindings
        base_bindings = list(self.base.get(context, {}).items())
        base_bindings.sort(key=lambda x: len(x[0]), reverse=True)

        for binding_keys, bindings in base_bindings:
            # Normalize binding_keys to tuple if it's a string (for compatibility)
            if isinstance(binding_keys, str):
                binding_keys = (binding_keys,)

            # Skip if any key in binding is already consumed
            if any(k in consumed for k in binding_keys):
                continue

            binding_set = set(binding_keys)

            # For single-key bindings, check all_axes first (for continuous axes like MIDI CCs)
            if len(binding_keys) == 1:
                key = binding_keys[0]
                if key in all_axes:
                    # Direct axis match (e.g., 'midi:cc_74')
                    value, _ = all_axes[key]

                    for binding in bindings:
                        if isinstance(binding.target, Axis):
                            cur_value = result.get(binding.target, 0.0)

                            if binding.transform:
                                new_value = binding.transform(cur_value, value)
                            else:
                                new_value = value

                            result[binding.target] = new_value
                            consumed.add(key)
                    continue

            # Check if binding matches (subset of held keys)
            if binding_set.issubset(expanded_held):
                # For axes, use the last key in the binding as the primary input
                if binding_keys:
                    primary_key = binding_keys[-1]

                    # Check if it's a direct axis (e.g., 'midi:cc_5')
                    if primary_key in all_axes:
                        value, _ = all_axes[primary_key]
                    else:
                        # It's a held key, treat as 1.0
                        value = 1.0

                    for binding in bindings:
                        if isinstance(binding.target, Axis):
                            cur_value = result.get(binding.target, 0.0)

                            if binding.transform:
                                # Use custom transform function
                                new_value = binding.transform(cur_value, value)
                            else:
                                # Default: direct pass-through
                                new_value = value

                            result[binding.target] = new_value

                            # Mark all keys in binding as consumed
                            consumed.update(binding_keys)

        return result

    def _load_defaults(self):
        print("""Load default bindings for all contexts""")
        # ===== MENU CONTEXT =====
        self.add_binding(InputContext.MENU, Action.NAVIGATE_UP, ('key:up',))
        self.add_binding(InputContext.MENU, Action.NAVIGATE_UP, ('key:w',))
        # CC 114: velocity > 0 triggers navigate_up, velocity < 0 triggers navigate_down
        # This is handled in resolve_actions_with_overlays by checking CC velocity
        self.add_binding(InputContext.MENU, Action.NAVIGATE_DOWN, ('key:down',))
        self.add_binding(InputContext.MENU, Action.NAVIGATE_DOWN, ('key:s',))
        self.add_binding(InputContext.MENU, Action.NAVIGATE_LEFT, ('key:left',))
        self.add_binding(InputContext.MENU, Action.NAVIGATE_LEFT, ('key:a',))
        self.add_binding(InputContext.MENU, Action.NAVIGATE_RIGHT, ('key:right',))
        self.add_binding(InputContext.MENU, Action.NAVIGATE_RIGHT, ('key:d',))
        self.add_binding(InputContext.MENU, Action.CONFIRM, ('key:enter',))
        self.add_binding(InputContext.MENU, Action.CONFIRM, ('key:space',))
        self.add_binding(InputContext.MENU, Action.CANCEL, ('key:escape',))
        self.add_binding(InputContext.MENU, Action.BACK, ('key:back',))

        # ===== VISUALIZATION CONTEXT =====
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_PITCH, ('key:w',), transform=passthrough(1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_PITCH, ('key:s',), transform=passthrough(-1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_PITCH, ('key:up',), transform=passthrough(1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_PITCH, ('key:down',), transform=passthrough(-1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_YAW, ('key:a',), transform=passthrough(-1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_YAW, ('key:d',), transform=passthrough(1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_YAW, ('key:left',), transform=passthrough(-1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_YAW, ('key:right',), transform=passthrough(1.0))
        # Zoom (shift+w/s/up/down) - using key lists
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ZOOM, ('key:shift', 'key:w',), transform=passthrough(1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ZOOM, ('key:shift', 'key:s',), transform=passthrough(-1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ZOOM, ('key:shift', 'key:up',), transform=passthrough(1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ZOOM, ('key:shift', 'key:down',), transform=passthrough(-1.0))

        # Roll (shift+a/d/left/right) - using key lists
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ROLL, ('key:shift', 'key:a',), transform=passthrough(-1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ROLL, ('key:shift', 'key:d',), transform=passthrough(1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ROLL, ('key:shift', 'key:left',), transform=passthrough(-1.0))
        self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ROLL, ('key:shift', 'key:right',), transform=passthrough(1.0))

        # Camera control - MIDI knobs 5-8 (when NOT in envelope mode)
        # CC numbers from midi_config.yml: 93, 18, 19, 16
        # These will be overridden by envelope overlay when 'p' is pressed
        # self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_PITCH, 'midi:cc_93', transform=inverted(2.0))  # Knob 5: pitch
        # self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_YAW, 'midi:cc_18', transform=inverted(2.0))    # Knob 6: yaw
        # self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ROLL, 'midi:cc_19', transform=inverted(2.0))   # Knob 7: roll
        # self.add_binding(InputContext.VISUALIZATION, Axis.CAMERA_ZOOM, 'midi:cc_16', transform=inverted(2.0))   # Knob 8: zoom

        # MIDI CC to parameter axes (default bindings)
        # These bind MIDIState CC numbers (0-7) to parameter axes
        # The MIDI config maps physical controller CCs to MIDIState CCs
        # MIDIInputSource generates axes like 'midi:cc_0', 'midi:cc_1', etc. from MIDIState
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM0, ('midi:cc_0',))
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM1, ('midi:cc_1',))
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM2, ('midi:cc_2',))
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM3, ('midi:cc_3',))
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM4, ('midi:cc_4',))
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM5, ('midi:cc_5',))
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM6, ('midi:cc_6',))
        self.add_binding(InputContext.VISUALIZATION, Axis.PARAM7, ('midi:cc_7',))
        
        # Additional MIDI bindings can be loaded from midi_config.yml (overrides defaults)
        self.add_binding(InputContext.VISUALIZATION, Axis.SEED, ('midi:chord_seed',))

        # Parameter control - keyboard increment/decrement (discrete actions)
        # param0: n/m
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM0, ('key:n',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM0, ('key:m',))
        # param1: ,/.
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM1, ('key:,',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM1, ('key:.',))
        # param2: ;/'
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM2, ('key:;',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM2, ('key:\'',))
        # param3: [/]
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM3, ('key:[',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM3, ('key:]',))

        # param4: shift+n/m - using key lists
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM4, ('key:shift', 'key:n',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM4, ('key:shift', 'key:m',))
        # param5: shift+,/. - using key lists
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM5, ('key:shift', 'key:,',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM5, ('key:shift', 'key:.',))
        # param6: shift+;/' - using key lists
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM6, ('key:shift', 'key:;',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM6, ('key:shift', 'key:\'',))
        self.add_binding(InputContext.VISUALIZATION, Action.DEC_PARAM7, ('key:shift', 'key:[',))
        self.add_binding(InputContext.VISUALIZATION, Action.INC_PARAM7, ('key:shift', 'key:]',))

        # Settings (discrete actions)
        self.add_binding(InputContext.MENU, Action.TOGGLE_DEBUG, ('key:i',))
        self.add_binding(InputContext.MENU, Action.TOGGLE_PREVIEW, ('key:p',))
        self.add_binding(InputContext.MENU, Action.TOGGLE_INPUT_FORWARDING, ('key:t',))

        self.add_binding(InputContext.VISUALIZATION, Action.TOGGLE_DEBUG, ('key:i',))
        self.add_binding(InputContext.VISUALIZATION, Action.RELOAD_SHADER, ('key:r',))
        self.add_binding(InputContext.VISUALIZATION, Action.INCREASE_BRIGHTNESS, ('key:b',))
        self.add_binding(InputContext.VISUALIZATION, Action.DECREASE_BRIGHTNESS, ('key:v',))
        self.add_binding(InputContext.VISUALIZATION, Action.INCREASE_GAMMA, ('key:h',))
        self.add_binding(InputContext.VISUALIZATION, Action.DECREASE_GAMMA, ('key:g',))
        self.add_binding(InputContext.VISUALIZATION, Action.INCREASE_FPS, ('key:=',))
        self.add_binding(InputContext.VISUALIZATION, Action.DECREASE_FPS, ('key:-',))
        self.add_binding(InputContext.VISUALIZATION, Action.TOGGLE_AUDIO, ('key:\\',))
        self.add_binding(InputContext.VISUALIZATION, Action.CANCEL, ('key:escape',))

        # Effect undo/redo
        self.add_binding(InputContext.VISUALIZATION, Action.UNDO_EFFECT, ('key:shift', 'key:-',))  # (shift + -) Undo effect
        self.add_binding(InputContext.VISUALIZATION, Action.REDO_EFFECT, ('key:shift', 'key:=',))  # (shift + =) Redo effect

        # ===== PROMPT CONTEXT =====
        # (Similar to menu for now)
        self.add_binding(InputContext.PROMPT, Action.CANCEL, ('key:escape',))
    
    def _load_effect_bindings(self):
        """Load effect bindings from effect_bindings.yml if it exists."""
        from cube.input.effect_bindings_loader import load_effect_bindings
        
        # Determine config path
        if self._effect_bindings_config_path is None:
            self._effect_bindings_config_path = Path(__file__).parent.parent.parent.parent / 'effect_bindings.yml'
        
        try:
            _, bindings = load_effect_bindings(self._effect_bindings_config_path)
            
            # Remove existing effect bindings for VISUALIZATION context
            # (only remove bindings that were previously loaded from effect_bindings.yml)
            for action in self._effect_binding_actions:
                raw_inputs = self.reverse.get(InputContext.VISUALIZATION, {}).get(action, [])
                for raw_input in raw_inputs[:]:  # Copy list to avoid modification during iteration
                    self.remove_binding(InputContext.VISUALIZATION, action, raw_input)
            
            # Clear the tracked effect binding actions
            self._effect_binding_actions.clear()
            
            # Add new bindings
            for binding in bindings:
                # Track this action as an effect binding
                self._effect_binding_actions.add(binding.action)
                
                for inp in binding.inputs:
                    # Convert input to tuple format if needed
                    if isinstance(inp, str):
                        raw_input = (inp,)
                    elif isinstance(inp, tuple):
                        raw_input = inp
                    else:
                        raw_input = (str(inp),)
                    
                    # Add binding (will override defaults if same action/input exists)
                    self.add_binding(
                        InputContext.VISUALIZATION,
                        binding.action,
                        raw_input
                    )
            
            if bindings:
                print(f"[BindingMap] Loaded {len(bindings)} effect bindings from {self._effect_bindings_config_path}")
            
            # Update mtime cache
            self._update_config_mtime()
        except Exception as e:
            # Silently fail if config doesn't exist or is invalid
            pass
    
    def _update_config_mtime(self) -> None:
        """Cache current effect bindings config mtime (if file exists)."""
        if self._effect_bindings_config_path is None:
            return
        try:
            self._last_config_mtime = self._effect_bindings_config_path.stat().st_mtime
        except FileNotFoundError:
            self._last_config_mtime = None
    
    def _maybe_reload_effect_bindings(self, dt: float) -> None:
        """Periodically check for changes to the effect bindings config on disk.
        
        This allows live-updating effect bindings from the remap tool without
        restarting the visualization process.
        
        Args:
            dt: Delta time since last check
        """
        if self._effect_bindings_config_path is None:
            return
        
        self._config_check_accumulator += dt
        if self._config_check_accumulator < 0.5:
            return
        
        self._config_check_accumulator = 0.0
        
        try:
            mtime = self._effect_bindings_config_path.stat().st_mtime
        except FileNotFoundError:
            # Config deleted; nothing to reload
            return
        
        if self._last_config_mtime is None:
            self._last_config_mtime = mtime
            return
        
        if mtime != self._last_config_mtime:
            self._last_config_mtime = mtime
            print(f"[BindingMap] Effect bindings config changed, reloading...")
            self._load_effect_bindings()
    
    def update(self, dt: float) -> None:
        """Update binding map (check for config file changes).
        
        Call this periodically (e.g., once per frame) to enable live reloading
        of effect bindings.
        
        Args:
            dt: Delta time since last update
        """
        self._maybe_reload_effect_bindings(dt)
