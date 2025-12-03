# Keyboard Input System

The input module provides a unified keyboard input abstraction for different platforms and input methods.

## Quick Reference: Shift Modifier on RPI/SSH

On Raspberry Pi over SSH, shift detection works differently than on macOS. Use any of these methods:

| Method | How to Use | Example |
|--------|------------|---------|
| **Z Key** (Easiest) | Press and hold `Z` | Hold `Z` + `W` for zoomed forward movement |
| **Uppercase Letters** | Hold Shift + letter | `Shift+W` sends `W`, detected as shift |
| **Shift+Arrows** | Use Shift + arrow keys | Works if your terminal supports it |

**Recommended:** Use the `Z` key as your zoom modifier on RPI - it's the most reliable method.

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

### `InputHandler` (Recommended - High-Level Interface)
Unified input handler that wraps keyboard state from display backend.
Provides a clean, decoupled way to handle both discrete key presses (menus)
and continuous key holds (shaders).

**Methods:**
- `update(events: dict)` - Update from display backend events
- `is_quit_requested() -> bool` - Check if quit was requested
- `is_key_pressed(*keys) -> bool` - Check if any key was pressed this frame
- `is_exit_requested() -> bool` - Check for escape/quit/back keys
- `is_key_held(*keys) -> bool` - Check if any key is held down
- `get_pressed_key() -> Optional[str]` - Get the pressed key
- `get_held_keys() -> List[str]` - Get all held keys
- `apply_to_shader_keyboard(keyboard)` - Apply input to shader camera

**Why use InputHandler?**
- Decouples input logic from controller
- Same interface for menu and shader input
- Clean, readable code
- Easy to test

### `Keyboard` (Abstract Base Class - Low-Level)
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

**Shift Key Detection on SSH:**
Terminal mode doesn't provide direct shift key events. Instead, shift is detected through:
1. **Shift+Arrow keys** - Terminal sends `ESC[1;2A` (up), `ESC[1;2B` (down), etc.
2. **Uppercase letters** - Pressing `Shift+W` sends `W`, which is detected as `w` with shift held
3. **Z key** - Use `z` or `Z` as an alternate shift modifier (easier to use over SSH)

**Usage examples on RPI:**
- Camera zoom in shader mode: Hold `Z` while moving with arrow keys or WASD
- Shift+arrow works if your terminal supports it
- Uppercase WASD (e.g., `W`, `A`, `S`, `D`) also sets shift

## Usage

### Using InputHandler (Recommended)
The InputHandler provides a unified, decoupled interface for all input processing:

```python
from cube.display import Display
from cube.input import InputHandler

# Create display and input handler
display = Display(64, 64, backend='pygame')
input = InputHandler()

running = True
while running:
    # Update input from display events
    events = display.handle_events()
    input.update(events)

    # Check for quit
    if input.is_quit_requested():
        running = False
        break

    # Menu mode: check for key presses
    if input.is_key_pressed('enter'):
        select_item()
    elif input.is_key_pressed('up'):
        move_selection_up()
    elif input.is_exit_requested():
        go_back()

    # Shader mode: check for held keys and apply to shader
    if input.is_key_pressed('reload'):
        reload_shader()

    # Apply continuous input to shader camera
    states = input.apply_to_shader_keyboard(shader_renderer.keyboard_input)
    shader_renderer.shift_pressed = states['shift']

    # Check for custom held keys
    if input.is_key_held('t'):
        toggle_mode()
```

### Backend Integration (Automatic)
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
  - **macOS/pygame:** Use physical Shift key
  - **RPI/SSH:** Use `Z` key, `Shift+arrows`, or uppercase letters (W/A/S/D)
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

## Benefits of InputHandler

### Before (Manual Event Handling):
```python
# Controller was tightly coupled to events dict format
events = display.handle_events()

if events['quit']:
    running = False

if events['key']:
    if events['key'] in ('escape', 'quit', 'back'):
        exit_mode()
    elif events['key'] == 'reload':
        reload_shader()

# Shader mode: manual key mapping
keys_held = events.get('keys', [])
keyboard.set_key_state('up', 'up' in keys_held or 'w' in keys_held)
keyboard.set_key_state('down', 'down' in keys_held or 's' in keys_held)
keyboard.set_key_state('left', 'left' in keys_held or 'a' in keys_held)
keyboard.set_key_state('right', 'right' in keys_held or 'd' in keys_held)
keyboard.set_key_state('forward', 'e' in keys_held)
keyboard.set_key_state('backward', 'c' in keys_held)
shader.shift_pressed = 'shift' in keys_held
```

### After (With InputHandler):
```python
# Clean, decoupled, testable
events = display.handle_events()
input.update(events)

if input.is_quit_requested():
    running = False

if input.is_exit_requested():
    exit_mode()
elif input.is_key_pressed('reload'):
    reload_shader()

# Shader mode: single call
states = input.apply_to_shader_keyboard(keyboard)
shader.shift_pressed = states['shift']
```

**Benefits:**
- **80% less code** - from 10+ lines to 2 lines for shader input
- **Same approach** - both menu and shader use the same methods
- **Decoupled** - controller doesn't know about events dict format
- **Testable** - easy to unit test without display backend
- **Readable** - `input.is_exit_requested()` vs `events['key'] in ('escape', 'quit', 'back')`

## Adding New Keyboard Types

To add a new keyboard implementation:

1. Create a new file in `src/cube/input/`
2. Subclass `Keyboard` abstract base class
3. Implement `poll()` and `cleanup()` methods
4. Export from `__init__.py`
5. Use in appropriate display backend

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
