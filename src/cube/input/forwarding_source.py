"""
Input forwarding source - forwards input from menu to visualization, filtering specific keys.

Used to redirect keyboard/midi input from menu window to visualization window
when the menu is focused but user wants to control visualization.
"""
from typing import Set, Optional
from .input_source import InputSource, InputState
from .midi_source import MIDIInputSource
import threading


class ForwardingInputSource(InputSource):
    """
    Forwards input from menu's input sources to visualization, filtering out specific keys.
    
    Used when input forwarding mode is enabled - allows controlling visualization
    from menu window even when visualization window is not focused.
    
    This source reads from cached input state that is updated on the main thread,
    avoiding thread-safety issues with pygame event handling.
    """
    
    def __init__(self, menu_input_manager, midi_state=None, filter_keys: Set[str] = None, priority: int = 50):
        """
        Initialize forwarding input source.
        
        Args:
            menu_input_manager: InputManager from menu window (to read cached state)
            midi_state: MIDIState instance (optional, for MIDI forwarding)
            filter_keys: Set of keys to filter out (e.g., {'key:t'})
            priority: Priority for conflict resolution (default: 50, between keyboard and MIDI)
        """
        self.menu_input_manager = menu_input_manager
        self.midi_state = midi_state
        self.filter_keys = filter_keys or set()
        self._priority = priority
        
        # Cached input state (updated on main thread, read from visualization thread)
        self._cached_keyboard_state: Optional[InputState] = None
        self._cache_lock = threading.Lock()
        
        # Create MIDI source if MIDI state is available (MIDI is thread-safe)
        self._midi_source: Optional[MIDIInputSource] = None
        if midi_state:
            self._midi_source = MIDIInputSource(midi_state, priority=100)
    
    @property
    def name(self) -> str:
        """Source name"""
        return 'menu_forwarding'
    
    @property
    def priority(self) -> int:
        """Priority for conflict resolution"""
        return self._priority
    
    def update_cache(self):
        """
        Update cached keyboard state from menu's input manager.
        
        This should be called on the main thread after menu's InputManager has polled.
        Gets raw input states from menu's InputManager's last poll (without polling again).
        """
        # Get raw input states from menu's InputManager's last poll
        # This avoids polling sources again, which would reset their internal state tracking
        keyboard_state = None
        raw_states = self.menu_input_manager.get_last_raw_states()
        for state in raw_states:
            if state.source_name == 'keyboard':
                keyboard_state = state
                break
        
        # Store cached state
        with self._cache_lock:
            self._cached_keyboard_state = keyboard_state
    
    def poll(self) -> InputState:
        """
        Poll menu's keyboard and MIDI, forward input, filtering out specified keys.
        
        Reads from cached keyboard state (updated on main thread) to avoid
        thread-safety issues with pygame event handling.
        
        Returns:
            InputState with forwarded input (filtered)
        """
        # Read cached keyboard state (updated on main thread)
        keyboard_state = None
        with self._cache_lock:
            keyboard_state = self._cached_keyboard_state
        
        # Poll MIDI source (this is safe, MIDI state is shared and thread-safe)
        midi_state = None
        if self._midi_source and self._midi_source.is_available():
            midi_state = self._midi_source.poll()
        
        # Combine and filter states
        all_pressed = set()
        all_released = set()
        all_held = set()
        all_axes = {}
        max_priority = 0
        
        if keyboard_state:
            # Filter keyboard input (only filter out 'key:t', forward everything else)
            # This forwards numeric keys (1-8) and shift, allowing effect toggles to work
            # Shifted numeric keys work because both 'key:shift' and 'key:1' are forwarded,
            # and the binding system matches tuples like ('key:shift', 'key:1') by checking
            # if both keys are in the held set
            filtered_pressed = {k for k in keyboard_state.pressed if k not in self.filter_keys}
            filtered_released = {k for k in keyboard_state.released if k not in self.filter_keys}
            filtered_held = {k for k in keyboard_state.held if k not in self.filter_keys}
            
            all_pressed.update(filtered_pressed)
            all_released.update(filtered_released)
            all_held.update(filtered_held)
            max_priority = max(max_priority, keyboard_state.source_priority)
        
        if midi_state:
            # MIDI input (no filtering needed, just forward)
            all_pressed.update(midi_state.pressed)
            all_released.update(midi_state.released)
            all_held.update(midi_state.held)
            all_axes.update(midi_state.axes)
            max_priority = max(max_priority, midi_state.source_priority)
        
        return InputState(
            source_name=self.name,
            source_priority=max_priority,
            pressed=all_pressed,
            released=all_released,
            held=all_held,
            axes=all_axes,
            quit_requested=False,  # Never forward quit from menu
            paste_text=None  # Don't forward paste
        )
    
    def is_available(self) -> bool:
        """Forwarding source is available when keyboard or MIDI is available"""
        keyboard_available = self._cached_keyboard_state is not None
        midi_available = self._midi_source and self._midi_source.is_available()
        return keyboard_available or midi_available
    
    def cleanup(self):
        """Clean up forwarding source"""
        if self._midi_source:
            self._midi_source.cleanup()

