"""
Central input manager with modal overlay support.

Coordinates all input sources and resolves to actions/axes.
Supports live remapping and modal overlays (envelope mode).
"""
from typing import List, Dict, Set, Optional, Union
from .actions import Action, Axis, InputContext, ActionState
from .input_source import InputSource, InputState
from .bindings import BindingMap, BindingOverlay

class InputManager:
    """
    Central input coordination hub.

    Pull-based API - consumers ask for values when needed.
    Supports modal overlays for temporary binding changes.

    Usage:
        manager = InputManager()
        manager.register_source(keyboard_source)
        manager.register_source(midi_source)
        manager.set_context(InputContext.VISUALIZATION)

        # In game loop:
        manager.poll()
        if manager.is_action_pressed(Action.TOGGLE_DEBUG):
            toggle_debug()
        zoom = manager.get_axis(Axis.CAMERA_ZOOM)
    """

    def __init__(self):
        """Initialize input manager"""
        self.sources = []
        self.bindings = BindingMap()
        self.overlay_stack = []
        self.context = InputContext.MENU
        self._actions = {}
        self._actions_pressed = set()
        self._actions_held = set()
        self._actions_released = set()
        self._axes = {}
        self._prev_actions = set()
        self._last_cc_values = {}
        self._quit = False
        self._paste = None

    def register_source(self, source: InputSource):
        """
        Add an input source.

        Sources are sorted by priority (highest first) for conflict resolution.

        Args:
            source: InputSource implementation
        """
        self.sources.append(source)
        self.sources.sort(key=lambda s: s.priority, reverse=True)

    def set_context(self, context: InputContext):
        """
        Switch input context.

        Different contexts have different bindings (menu vs visualization).

        Args:
            context: New input context
        """
        self.context = context

    def poll(self):
        """
        Poll all sources and resolve to actions/axes.

        Call this once per frame before querying input state.
        Adds velocity tracking to all CC signals and tracks modifiers.
        """
        raw_states = [s.poll() for s in self.sources if s.is_available()]

        self._actions = self.bindings.resolve_actions_with_overlays(
            raw_states, self.context, self.overlay_stack
        )
        self._axes = self.bindings.resolve_axes_with_overlays(
            raw_states, self.context, self.overlay_stack
        )
        current_actions = set(self._actions.keys())
        self._actions_pressed = {
            action
            for action, state in self._actions.items()
            if state == ActionState.PRESSED or action not in self._prev_actions
        }
        self._actions_held = {
            action
            for action, state in self._actions.items()
            if state == ActionState.HELD
        }
        self._actions_released = self._prev_actions - current_actions
        self._prev_actions = current_actions.copy()
        self._quit = any((s.quit_requested for s in raw_states))
        self._paste = next((s.paste_text for s in raw_states if s.paste_text), None)

    def get_axis(self, axis: Axis, default: float=0.0) -> float:
        """
        Get current axis value.

        Args:
            axis: Axis to query
            default: Value if axis not active

        Returns:
            Axis value (typically 0.0-1.0 or -1.0-1.0)
        """
        return self._axes.get(axis, default)

    def is_action_pressed(self, action: Action) -> bool:
        """
        Check if action was pressed this frame.

        Args:
            action: Action to check

        Returns:
            True if pressed this frame
        """
        return action in self._actions_pressed

    def is_action_held(self, action: Action) -> bool:
        """
        Check if action is currently held.

        Args:
            action: Action to check

        Returns:
            True if held down
        """
        return action in self._actions_held or action in self._actions_pressed

    def is_action_released(self, action: Action) -> bool:
        """
        Check if action was released this frame.

        Args:
            action: Action to check

        Returns:
            True if released this frame
        """
        return action in self._actions_released

    def get_pressed_actions(self) -> Set[Action]:
        """
        Get all actions pressed this frame (for efficient iteration).

        Returns:
            Set of pressed actions
        """
        return self._actions_pressed.copy()

    def get_held_actions(self) -> Set[Action]:
        """
        Get all actions currently held (for efficient iteration).

        Returns:
            Set of held actions
        """
        return self._actions_held.copy()

    def get_released_actions(self) -> Set[Action]:
        """
        Get all actions released this frame (for efficient iteration).

        Returns:
            Set of released actions
        """
        return self._actions_released.copy()

    def is_quit_requested(self) -> bool:
        """
        Check if quit was requested (window close, Ctrl+C).

        Returns:
            True if quit requested
        """
        return self._quit

    def get_paste_text(self) -> Optional[str]:
        """
        Get pasted text if any (Cmd+V / Ctrl+V).

        Returns:
            Pasted text or None
        """
        return self._paste

    def push_overlay(self, name: str, bindings: Dict[tuple[str], Union[Action, Axis]]):
        """
        Push a temporary binding overlay.

        Used for modal input modes like envelope editor.
        Overlays are checked before base bindings.

        Args:
            name: Overlay identifier (e.g., 'envelope_editor')
            bindings: {tuple[str]: target} mappings

        Example:
            manager.push_overlay('envelope_editor', {
                ('midi:cc_5'): Axis.ENVELOPE_ATTACK,
                ('midi:cc_6'): Axis.ENVELOPE_DECAY,
            })
        """
        overlay = BindingOverlay(name, bindings, self.context)
        self.overlay_stack.append(overlay)

    def pop_overlay(self, name: Optional[str]=None):
        """
        Remove a binding overlay.

        Args:
            name: Overlay to remove (None = pop top of stack)

        Example:
            manager.pop_overlay('envelope_editor')
        """
        if name is None:
            if self.overlay_stack:
                self.overlay_stack.pop()
        else:
            self.overlay_stack = [o for o in self.overlay_stack if o.name != name]

    def has_overlay(self, name: str) -> bool:
        """
        Check if an overlay is active.

        Args:
            name: Overlay identifier

        Returns:
            True if overlay is in stack
        """
        return any((o.name == name for o in self.overlay_stack))

    def remap(self, target: Union[Action, Axis], raw_input: str, replace: bool=True):
        """
        Change physical input → action/axis binding at runtime.

        Args:
            target: Action or Axis to remap
            raw_input: New input (e.g., 'midi:note_72', 'midi:cc_5')
            replace: If True, remove other bindings for this target

        Example:
            # Move flash trigger from pad 1 to pad 3
            manager.remap(Action.TOGGLE_FLASH, 'midi:note_39')

            # Move param0 from CC1 to CC5
            manager.remap(Axis.PARAM0, 'midi:cc_5')
        """
        if replace:
            old_inputs = self.bindings.get_raw_inputs(target, self.context)
            for old_input in old_inputs:
                self.bindings.remove_binding(self.context, target, old_input)
        self.bindings.add_binding(self.context, target, raw_input)

    def get_current_binding(self, target: Union[Action, Axis]) -> List[str]:
        """
        Get raw inputs currently bound to a target.

        Useful for displaying current mappings in UI.

        Args:
            target: Action or Axis to query

        Returns:
            List of raw input strings (e.g., ['midi:cc_5', 'key:n'])
        """
        return self.bindings.get_raw_inputs(target, self.context)

    def cleanup(self):
        """Clean up all input sources"""
        for source in self.sources:
            source.cleanup()