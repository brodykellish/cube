"""
Hardware keyboard input using evdev for real-time game controls.

Provides true simultaneous key detection and proper modifier support
by reading directly from keyboard hardware devices.
"""
import os
import select
from typing import Dict, Set, Optional
from pathlib import Path


class EvdevKeyboardInput:
    """
    Read keyboard input directly from hardware using evdev.

    Provides:
    - True simultaneous multi-key detection
    - Proper shift/ctrl/alt modifiers
    - Real key-down and key-up events
    - No terminal interference
    """

    def __init__(self):
        """Initialize evdev keyboard reader."""
        self.device = None
        self.pressed_keys = set()
        self.key_states = {
            'up': False,
            'down': False,
            'left': False,
            'right': False,
            'forward': False,
            'backward': False,
            'shift': False,
            'ctrl': False,
            'alt': False
        }
        self.key_map = {}
        
        try:
            import evdev
            self.evdev = evdev
        except ImportError:
            raise RuntimeError('evdev not installed. Run: pip install evdev')
        else:
            self._find_keyboard()
            self.key_map = {
                self.evdev.ecodes.KEY_UP: 'up',
                self.evdev.ecodes.KEY_DOWN: 'down',
                self.evdev.ecodes.KEY_LEFT: 'left',
                self.evdev.ecodes.KEY_RIGHT: 'right',
                self.evdev.ecodes.KEY_W: 'up',
                self.evdev.ecodes.KEY_S: 'down',
                self.evdev.ecodes.KEY_A: 'left',
                self.evdev.ecodes.KEY_D: 'right',
                self.evdev.ecodes.KEY_LEFTSHIFT: 'shift',
                self.evdev.ecodes.KEY_RIGHTSHIFT: 'shift',
                self.evdev.ecodes.KEY_LEFTCTRL: 'ctrl',
                self.evdev.ecodes.KEY_RIGHTCTRL: 'ctrl',
                self.evdev.ecodes.KEY_LEFTALT: 'alt',
                self.evdev.ecodes.KEY_RIGHTALT: 'alt',
            }
            print(f'Evdev keyboard input initialized: {self.device.name}')

    def _find_keyboard(self):
        """Find the keyboard device."""
        devices = [self.evdev.InputDevice(path) for path in self.evdev.list_devices()]
        for device in devices:
            capabilities = device.capabilities(verbose=False)
            if self.evdev.ecodes.EV_KEY not in capabilities:
                continue
            keys = capabilities[self.evdev.ecodes.EV_KEY]
            has_letters = self.evdev.ecodes.KEY_A in keys and self.evdev.ecodes.KEY_Z in keys
            has_arrows = self.evdev.ecodes.KEY_UP in keys
            if has_letters or has_arrows:
                import fcntl
                fd = device.fd
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                self.device = device
                print(f'Found keyboard: {device.name} ({device.path})')
                return
        
        raise RuntimeError('No keyboard device found. Make sure you have permission to access /dev/input/event*')

    def grab(self):
        """Grab exclusive keyboard access (blocks other programs from seeing keys)."""
        if self.device:
            try:
                self.device.grab()
                print('Evdev keyboard grabbed (exclusive mode)')
            except Exception:
                pass

    def ungrab(self):
        """Release exclusive keyboard access."""
        if self.device:
            try:
                self.device.ungrab()
                print('Evdev keyboard released')
            except Exception:
                pass

    def update(self):
        """
        Update keyboard state by reading all available events.
        Call this every frame to keep key states current.
        """
        if not self.device:
            return
        
        try:
            events_read = 0
            for event in self.device.read():
                if event.type == self.evdev.ecodes.EV_KEY:
                    self._handle_key_event(event)
                    events_read += 1
            if events_read > 0:
                print(f'[EVDEV] Read {events_read} key events')
        except BlockingIOError:
            pass
        except Exception as e:
            print(f'[EVDEV] Error reading events: {e}')

    def _handle_key_event(self, event):
        """Handle a single key event."""
        key_code = event.code
        is_pressed = event.value in (1, 2)
        key_name = self.key_map.get(key_code)
        if key_name:
            self.key_states[key_name] = is_pressed
            action = 'pressed' if is_pressed else 'released'
            print(f'[EVDEV] Key {key_name} {action}')

    def is_pressed(self, key: str) -> bool:
        """Check if a key is currently pressed."""
        return self.key_states.get(key, False)

    def get_key_state(self, key: str) -> bool:
        """Get the current state of a key."""
        return self.key_states.get(key, False)

    def cleanup(self):
        """Release keyboard device."""
        if self.device:
            try:
                self.device.ungrab()
                self.device.close()
            except Exception:
                pass
        self.device = None
