# Async Shader Generation - UI Responsiveness Fix

## Problem

The application was unresponsive while waiting for Claude to generate shaders. Users could not interact with the UI, and there was no visible loading animation during the (potentially long) API call.

## Solution

Implemented asynchronous shader generation using Python threading, allowing the UI to remain responsive while Claude generates shaders in the background.

## Changes Made

### 1. Added Threading Support (src/cube/menu/prompt_menu.py)

**Imports**:
```python
import threading
```

**New Instance Variables** (lines 81-85):
```python
# Async generation state
self.generation_thread: Optional[threading.Thread] = None
self.generation_result: Optional[ShaderGenerationResult] = None
self.generation_complete = False
self.pending_action: Optional[MenuAction] = None
```

### 2. Refactored Shader Generation Method

**Before**: Synchronous blocking call
```python
def _handle_shader_generation(self, user_prompt: str) -> Optional[MenuAction]:
    result = agent.generate_shader(...)  # BLOCKS UI
    # Process result...
    return action
```

**After**: Async with threading (lines 325-419)
```python
def _handle_shader_generation(self, user_prompt: str) -> Optional[MenuAction]:
    """Starts async generation, returns immediately."""
    self.is_generating = True
    self.text_box.append_text(f"cube: ...")  # Loading message

    # Start background thread
    self.generation_thread = threading.Thread(
        target=self._generate_shader_async,
        args=(user_prompt,),
        daemon=True
    )
    self.generation_thread.start()
    return None  # Returns immediately!

def _generate_shader_async(self, user_prompt: str):
    """Background thread worker."""
    # Call agent (blocks thread, not UI)
    result = agent.generate_shader(...)

    # Store result for main thread
    self.generation_result = result
    self.generation_complete = True
```

### 3. Updated update() Method to Process Results

**Enhanced update() method** (lines 520-588):
```python
def update(self, dt: float) -> Optional[MenuAction]:
    """Update animations and check for async completion."""

    # Animate cursor blinking (0.5s interval)
    # ...

    # Animate loading ellipsis at 1 FPS (. .. ... ....)
    if self.is_generating:
        self.loading_animation_time += dt
        if self.loading_animation_time >= 1.0:  # Update every 1 second
            # Cycle dots in loading message
            # ...

    # Check for generation completion
    if self.generation_complete and self.generation_result:
        result = self.generation_result

        # Reset state
        self.is_generating = False
        self.generation_complete = False

        # Process result
        if result.success:
            return LaunchVisualizationAction(...)
        else:
            self.text_box.append_text(f"ERROR: {result.error}")

    return None
```

### 4. Added Menu Update System

**MenuNavigator.update()** (src/cube/menu/navigation.py:88-104):
```python
def update(self, dt: float) -> Optional[MenuAction]:
    """Update current menu state (if it has an update method)."""
    if self.current_state and hasattr(self.current_state, 'update'):
        result = self.current_state.update(dt)
        if isinstance(result, MenuAction):
            return self.handle_action(result)
    return None
```

**Controller Integration** (src/cube/controller.py:184-187):
```python
# Update menu state (for animations, async operations, etc.)
action = self.menu_navigator.update(dt)
if action:
    running = self._handle_action(action)
```

## How It Works

### Workflow

```
User: "create a rotating sphere"
  ↓
[Main Thread] _handle_shader_generation()
  ├─ Set is_generating = True
  ├─ Show loading message: "cube: ..."
  ├─ Start background thread
  └─ Return immediately

[Background Thread] _generate_shader_async()
  ├─ Call Claude API (BLOCKING, but only this thread)
  ├─ Wait for response...
  ├─ Process result
  └─ Set generation_complete = True

[Main Thread] update() called every frame (~60 FPS)
  ├─ Animate cursor blink
  ├─ Animate ellipsis: . .. ... ....
  └─ Check if generation_complete?
      ├─ Yes: Process result, launch visualization
      └─ No: Continue waiting

User Interface: FULLY RESPONSIVE throughout!
```

### Key Features

1. **Non-Blocking**: API calls happen in background thread
2. **Input Disabled**: `is_generating` flag prevents input during generation
3. **Visual Feedback**: Animated ellipsis shows progress
4. **Safe Threading**: Result processed in main thread only
5. **Error Handling**: Exceptions caught and displayed

## UI Behavior

### During Generation:
- ✅ Loading animation visible: "cube: . .. ... ...." (updates at 1 FPS)
- ✅ Text input disabled (cursor hidden)
- ✅ Window remains responsive
- ✅ Can still render and update UI at 60 FPS
- ❌ Cannot type new prompts (prevented by `is_generating`)
- ⏱️ Ellipsis cycles every second for smooth, readable animation

### On Completion:
- ✅ Loading message removed
- ✅ Success/error message shown
- ✅ Input re-enabled
- ✅ Visualization launches automatically (if successful)

## Thread Safety

- **Background Thread**: Only writes to `generation_result` and `generation_complete`
- **Main Thread**: Only reads these variables, processes in `update()`
- **No Locks Needed**: Simple flag-based synchronization
- **Daemon Thread**: Automatically cleaned up on exit

## Testing

The async system works for:
- ✅ New shader generation (with validation)
- ✅ Shader editing
- ✅ Error retry loops (3 attempts)
- ✅ Compilation error detection

## Performance Impact

- **Before**: UI frozen for 5-30 seconds during generation
- **After**: UI responsive, ~60 FPS maintained
- **Memory**: Minimal (one thread + result object)
- **CPU**: Background thread only active during generation
- **Animation**: Loading ellipsis updates at 1 FPS (reduced from 60 FPS for readability)

## Future Improvements

Potential enhancements:
- Progress indicators (e.g., "Attempt 2/3...")
- Cancel button to abort generation
- Queue multiple shader requests
- Show partial results during streaming API calls
