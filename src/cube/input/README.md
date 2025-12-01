# Keyboard Input System

The input module provides a unified keyboard input abstraction for different platforms and input methods.

## Architecture

```
┌─────────────────────────────────────────┐
│          InputHandler                   │  ← High-level unified interface
│  (Decoupled input processing)           │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│     Display Backend Events              │
│     {'quit': bool, 'key': str,          │
│      'keys': list}                      │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│    Keyboard (Abstract Base Class)       │
├─────────────────────────────────────────┤
│  PygameKeyboard - pygame events         │
│  SSHKeyboard - Terminal input           │
└─────────────────────────────────────────┘
```

## Key Components

### `Keyboard` (Abstract Base Class)
Base class defining the keyboard interface:
- `poll() -> KeyboardState` - Poll for keyboard input
- `cleanup()` - Clean up resources

### `KeyboardState`
Represents the current keyboard state:
- `quit: bool` - Whether quit was requested
- `key_press: Optional[str]` - Single key pressed this frame
- `keys_held: List[str]` - All keys currently held down

### `PygameKeyboard`
Implementation for local macOS development:
- Uses pygame's event system
- Captures both key press events and held keys
- Automatically initialized by `PygameBackend`

### `SSHKeyboard`
Implementation for remote RPi control:
- Reads raw terminal input via termios
- Parses escape sequences for arrow keys
- Handles SSH terminal input properly
- Automatically initialized by `PiomatterBackend`

## Usage

### Automatic Usage (Recommended)
The keyboard is automatically configured based on the display backend:

```python
from cube.display import Display

# On macOS with pygame backend -> PygameKeyboard
display = Display(64, 64, backend='pygame')

# On RPi with piomatter backend -> SSHKeyboard
display = Display(64, 64, backend='piomatter')

# Poll for input
events = display.handle_events()
if events['quit']:
    break
if events['key'] == 'up':
    # Handle up key
    pass
```

### Manual Usage (Advanced)
You can also use the keyboard implementations directly:

```python
from cube.input import PygameKeyboard, SSHKeyboard
import pygame

# Pygame keyboard
pygame.init()
keyboard = PygameKeyboard(pygame)

while True:
    state = keyboard.poll()

    if state.quit:
        break

    if state.key_press:
        print(f"Key pressed: {state.key_press}")

    if 'w' in state.keys_held:
        print("W is held down")

keyboard.cleanup()
```

```python
from cube.input import SSHKeyboard

# SSH terminal keyboard
keyboard = SSHKeyboard()

try:
    while True:
        state = keyboard.poll()

        if state.quit:
            break

        if state.key_press:
            print(f"Key pressed: {state.key_press}")
finally:
    keyboard.cleanup()  # Restore terminal settings
```

## Standard Key Names

All keyboard implementations map hardware-specific keys to standard names:

### Navigation
- `'up'`, `'down'`, `'left'`, `'right'` - Arrow keys and WASD
- `'w'`, `'a'`, `'s'`, `'d'` - WASD keys (also available separately)

### Actions
- `'enter'` - Enter/Return (also Space in some contexts)
- `'escape'` - ESC key
- `'back'` - B key (menu back navigation)
- `'quit'` - Q key or Ctrl+C
- `'reload'` - R key (shader reload)

### Camera Control
- `'e'` - Forward movement
- `'c'` - Backward movement

### Modifiers
- `'shift'` - Shift key (zoom modifier)
- `'ctrl'` - Control key
- `'alt'` - Alt key

### Other
- `'t'` - Toggle (mode cycling)
- `'space'` - Space bar
- `'0'-'9'` - Number keys
- `'f1'-'f12'` - Function keys

## Implementation Details

### PygameKeyboard
- Maps pygame.K_* constants to standard key names
- Handles both `KEYDOWN` events (single press) and `get_pressed()` (held keys)
- Properly handles left/right variants of modifier keys (LSHIFT/RSHIFT)

### SSHKeyboard
- Uses `termios` to set terminal in cbreak mode
- Non-blocking read from stdin using `fcntl`
- Parses ANSI escape sequences for arrow keys
- Simulates "held keys" for one frame (terminal doesn't provide key-up events)
- Properly restores terminal settings on cleanup

## Backend Integration

The display backends automatically configure the appropriate keyboard:

**src/cube/display/pygame_backend.py:**
```python
from ..input.pygame_keyboard import PygameKeyboard

class PygameBackend(DisplayBackend):
    def __init__(self, ...):
        self.keyboard = PygameKeyboard(pygame)

    def handle_events(self) -> dict:
        state = self.keyboard.poll()
        return {
            'quit': state.quit,
            'key': state.key_press,
            'keys': state.keys_held
        }
```

**src/cube/display/piomatter_backend.py:**
```python
from ..input.ssh_keyboard import SSHKeyboard

class PiomatterBackend(DisplayBackend):
    def __init__(self, ...):
        self.keyboard = SSHKeyboard()

    def handle_events(self) -> dict:
        state = self.keyboard.poll()
        return {
            'quit': state.quit,
            'key': state.key_press,
            'keys': state.keys_held
        }
```

## Adding New Keyboard Types

To add a new keyboard implementation:

1. Create a new file in `src/cube/input/`
2. Subclass `Keyboard` abstract base class
3. Implement `poll()` and `cleanup()` methods
4. Map hardware-specific keys to `STANDARD_KEY_NAMES`
5. Export from `__init__.py`
6. Use in appropriate display backend

Example:
```python
from .keyboard import Keyboard, KeyboardState

class GPIOKeyboard(Keyboard):
    """Keyboard implementation using GPIO buttons."""

    def __init__(self, pin_mapping):
        self.pins = pin_mapping
        # Setup GPIO

    def poll(self) -> KeyboardState:
        state = KeyboardState()
        # Read GPIO pins
        # Map to key names
        return state

    def cleanup(self):
        # Cleanup GPIO
        pass
```
