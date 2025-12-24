<!-- a86e9557-7aed-4f38-bdf8-4e4360602e82 9e36671a-c690-4fd5-b556-6d0f13fc96ba -->
# Decouple Menu from Visualization - Simplified Approach

## Architecture Overview

- **Pygame window**: Menu/pipeline builder UI (always visible)
- **Pyglet window**: Visualization rendering (runs independently)
- **Input routing**: Keyboard follows window focus, MIDI always goes to visualization
- **Visualization thread**: Runs independently, renderer stays alive (parameters/effects persist)

## Phase 1: Remove Multi-Window Abstraction

### 1.1 Remove DisplayMode Abstraction

- **Files to remove**: 
  - `src/cube/display/display_mode.py`
  - `src/cube/display/multi_window_mode.py`
  - `src/cube/display/multi_window_pygame.py`
- **Files to keep**: Concrete backends (`pygame_backend.py`, `pyglet_backend.py`)

### 1.2 Update Controller Display Usage

- **File**: `src/cube/controller.py`
- Remove all DisplayMode references
- Directly use pygame/pyglet backends

## Phase 2: Create Separate Windows

### 2.1 Create MenuWindow (Pygame)

- **File**: `src/cube/display/menu_window.py` (new)
- Wraps `PygameBackend`
- Simple interface:
  - `is_focused()` - Check if window has focus (pygame.mouse.get_focused() or pygame.key.get_focused())
  - `handle_events()` - Poll pygame events, return keyboard state
  - `show_framebuffer()` - Display menu framebuffer
  - `cleanup()` - Clean up pygame

### 2.2 Create VisualizationWindow (Pyglet)

- **File**: `src/cube/display/visualization_window.py` (new)
- Wraps `PygletBackend`
- Simple interface:
  - `is_focused()` - Check if window has focus (window.has_exit or focus events)
  - `poll()` - Poll pyglet events, return keyboard state
  - `display()` - Display visualization framebuffer
  - `cleanup()` - Clean up pyglet

### 2.3 Update Controller

- **File**: `src/cube/controller.py`
- Create `menu_window` (MenuWindow instance)
- Create `viz_window` (VisualizationWindow instance)
- Each manages its own display backend independently

## Phase 3: Input Routing Strategy

### 3.1 Keyboard Input Routing

**Principle**: Only the focused window processes keyboard input

- **MenuWindow focused**:
  - Keyboard events → `menu_input_manager` (MENU context)
  - Menu can navigate, select, type in prompt, etc.

- **VisualizationWindow focused**:
  - Keyboard events → `viz_input_manager` (VISUALIZATION context)
  - Visualization handles camera, params, effects, etc.

**Implementation**:

- Each window polls its own keyboard events
- Controller checks `menu_window.is_focused()` vs `viz_window.is_focused()`
- Route keyboard to appropriate InputManager based on focus
- Both windows can poll simultaneously, but only focused one's InputManager processes actions

### 3.2 MIDI Input Routing

**Principle**: MIDI always goes to visualization (global/system-level)

- MIDI is not window-specific (system-level device)
- Visualization needs MIDI for live parameter control
- Menu rarely needs MIDI (can add later if needed)

**Implementation**:

- Create `viz_input_manager` (InputManager) for visualization
- Create `menu_input_manager` (InputManager) for menu
- Register MIDI source only with `viz_input_manager`
- Visualization always receives MIDI regardless of focus

### 3.3 Separate Input Managers

- **File**: `src/cube/controller.py`
- `menu_input_manager = InputManager()` - MENU context
- `viz_input_manager = InputManager()` - VISUALIZATION context
- MenuWindow keyboard → `menu_input_manager`
- VisualizationWindow keyboard → `viz_input_manager` (only when focused)
- MIDI source → `viz_input_manager` (always)

**How Bindings Work with Two InputManagers**:

Each `InputManager` instance has its own `BindingMap`:
- `menu_input_manager.bindings` - Separate BindingMap instance
- `viz_input_manager.bindings` - Separate BindingMap instance

**Binding Initialization**:
- Each BindingMap loads the same default bindings in `__init__()`:
  - `_load_defaults()` - Loads bindings for MENU and VISUALIZATION contexts
  - `_load_effect_bindings()` - Loads effect bindings from config
- Both InputManagers end up with identical default bindings
- But they're separate instances (independent)

**Context-Based Resolution**:
- Each InputManager has a `context` property:
  - `menu_input_manager.context = InputContext.MENU`
  - `viz_input_manager.context = InputContext.VISUALIZATION`
- When `poll()` is called, it resolves bindings ONLY for that InputManager's context:
  ```python
  # In menu_input_manager.poll():
  self._actions = self.bindings.resolve_actions_with_overlays(
      raw_states, self.context,  # Uses InputContext.MENU
      self.overlay_stack
  )
  
  # In viz_input_manager.poll():
  self._actions = self.bindings.resolve_actions_with_overlays(
      raw_states, self.context,  # Uses InputContext.VISUALIZATION
      self.overlay_stack
  )
  ```

**Result**:
- `menu_input_manager` only resolves MENU bindings (e.g., `NAVIGATE_UP`, `CONFIRM`)
- `viz_input_manager` only resolves VISUALIZATION bindings (e.g., `CAMERA_PITCH`, `TOGGLE_FLASH`)
- Same key can map to different actions in each context:
  - `'key:w'` in MENU → `NAVIGATE_UP`
  - `'key:w'` in VISUALIZATION → `CAMERA_PITCH` axis
- No conflicts because they're separate instances resolving different contexts

**Input Source Registration**:
- Each InputManager registers its own input sources:
  - `menu_input_manager.register_source(keyboard_source)` - MenuWindow keyboard
  - `viz_input_manager.register_source(keyboard_source)` - VisualizationWindow keyboard (when focused)
  - `viz_input_manager.register_source(midi_source)` - MIDI (always active)
- Sources are polled independently by each InputManager

**Binding Modifications**:
- Changes to one InputManager's bindings don't affect the other:
  - `menu_input_manager.remap(Action.NAVIGATE_UP, 'key:j')` - Only affects menu_input_manager
  - `viz_input_manager.remap(Axis.CAMERA_PITCH, 'key:j')` - Only affects viz_input_manager
- Each can have different custom bindings
- Effect bindings loaded from config apply to both (but they're separate copies)

**Example Flow**:
```python
# Initialization
menu_input_manager = InputManager()
menu_input_manager.set_context(InputContext.MENU)
menu_input_manager.register_source(menu_keyboard_source)

viz_input_manager = InputManager()
viz_input_manager.set_context(InputContext.VISUALIZATION)
viz_input_manager.register_source(viz_keyboard_source)
viz_input_manager.register_source(midi_source)

# In main loop (menu thread)
if menu_window.is_focused():
    menu_input_manager.poll()
    if menu_input_manager.is_action_pressed(Action.NAVIGATE_UP):
        # 'key:w' or 'key:up' pressed → navigate menu up
        menu.navigate_up()

# In visualization thread
viz_input_manager.poll()
if viz_input_manager.is_action_pressed(Action.TOGGLE_FLASH):
    # MIDI pad or keyboard → toggle flash effect
    effect_manager.toggle_flash()
camera_pitch = viz_input_manager.get_axis(Axis.CAMERA_PITCH)
# 'key:w' pressed → camera_pitch = 1.0 (if viz window focused)
```

## Phase 4: Threading Architecture

### 4.1 Thread Structure

**Main Thread (Root Thread)**:
- **Runs**: Pygame menu window
- **Owns**: MenuWindow, menu_input_manager, menu state
- **OpenGL Context**: None (pygame uses SDL software rendering, no OpenGL)
- **Responsibilities**:
  - Polls `menu_window.handle_events()` (pygame event loop)
  - Updates `menu_input_manager.poll()` (only when menu focused)
  - Handles menu navigation, pipeline builder UI
  - Renders menu UI to `menu_window.show_framebuffer()`
  - Manages debug log display (reads from shared log_lines)
  - Coordinates with VisualizationRunner (deploys pipelines, queries state)
- **Why main thread**: Pygame is single-threaded and simpler to manage in main thread
- **Thread name**: `MainThread` (default Python main thread)

**Visualization Thread (Daemon Thread)**:
- **Runs**: Pyglet visualization window
- **Owns**: VisualizationWindow, DAGRenderer, viz_input_manager, effect_manager, param_source
- **OpenGL Context**: Created automatically when pyglet window is created IN THIS THREAD
- **Responsibilities**:
  - **CRITICAL**: Creates VisualizationWindow (and thus pyglet window) INSIDE this thread
  - Polls `viz_window.poll()` (pyglet events via `window.dispatch_events()`)
  - Updates `viz_input_manager.poll()` (keyboard when focused + MIDI always)
  - Processes pipeline deployment queue (thread-safe)
  - Updates renderer (camera, params, effects)
  - Renders frames to `viz_window.display()`
  - Keeps renderer alive (persists parameters/effects)
- **Why separate thread**: Runs independently, doesn't block menu
- **Thread name**: `VisualizationThread` (set explicitly)
- **Daemon**: Yes (allows main thread to exit cleanly)

### 4.1.1 OpenGL Context Management

**Key Constraint**: OpenGL contexts are thread-local and must be created in the thread where they'll be used.

**Solution**:
- **Pygame**: Doesn't use OpenGL (uses SDL software rendering) → No OpenGL context in main thread ✅
- **Pyglet**: Creates OpenGL context automatically when window is created
- **Critical**: Pyglet window MUST be created INSIDE the visualization thread, not before starting the thread
- When `pyglet.window.Window()` is called in a thread, the OpenGL context is automatically created in that thread
- This avoids macOS constraints (context created where it's used, not on main thread)

**Why This Works**:
- Each thread has its own independent OpenGL context
- No context sharing needed (they render different things)
- No conflicts because contexts are thread-local
- macOS is happy because context is created in the thread that uses it

### 4.2 Thread Lifecycle

**Initialization (Main Thread)**:
1. Create shared debug log infrastructure (log_lines, log_lock)
2. Redirect stdout to thread-safe capture (before any threads start)
3. Create VisualizationRunner instance (does NOT create pyglet window yet)
4. Create MenuWindow instance (creates pygame window in main thread)
5. Call `visualization_runner.start()` (launches daemon thread, which creates pyglet window)
6. Enter main menu loop

**Main Thread Loop**:
```python
while running:
    # Poll menu window events
    menu_window.handle_events()
    
    # Update menu input (only if menu focused)
    if menu_window.is_focused():
        menu_input_manager.poll()
        # Handle menu actions
    
    # Render menu UI
    menu_window.show_framebuffer(menu_framebuffer)
    
    # Check for pipeline deployments (from menu actions)
    # visualization_runner.deploy_pipeline(config) if needed
    
    # Display debug logs (read from shared log_lines with lock)
    # menu can render log_lines[-100:] in overlay
```

**Visualization Thread Loop** (inside VisualizationRunner):
```python
def _run_loop(self):
    """Main visualization thread loop - CRITICAL: pyglet window created HERE"""
    # CRITICAL: Create pyglet window IN THIS THREAD (creates OpenGL context here)
    self._viz_window = VisualizationWindow(...)
    
    # Create renderer (uses OpenGL context from pyglet window)
    self._renderer = DAGRenderer(...)
    
    # Create input manager
    self._viz_input_manager = InputManager(context=VISUALIZATION)
    
    # Register MIDI source (always active)
    # ... register MIDI ...
    
    # Main render loop
    while not self._stop_flag.is_set():
        # Poll pyglet events
        self._viz_window.poll()
        
        # Update visualization input (keyboard + MIDI)
        self._viz_input_manager.poll()
        
        # Check pipeline deployment queue
        if not self._pipeline_queue.empty():
            config = self._pipeline_queue.get_nowait()
            self._deploy_pipeline_internal(config)
        
        # Update renderer from input
        # Handle camera, params, effects from viz_input_manager
        
        # Render frame
        self._renderer.render()
        
        # Display to pyglet window
        self._viz_window.display(self._renderer.framebuffer)
        
        # FPS limit
        time.sleep(1.0 / target_fps)
    
    # Cleanup (still in visualization thread)
    self._renderer.cleanup()
    self._viz_window.cleanup()
```

**Shutdown (Main Thread)**:
1. Set `visualization_runner._stop_flag = True`
2. Call `visualization_runner.stop()` (waits for thread with timeout, e.g., 5 seconds)
3. Cleanup MenuWindow
4. Restore original stdout
5. Exit

### 4.3 Create VisualizationRunner

- **File**: `src/cube/render/visualization_runner.py` (new)
- Runs in separate daemon thread
- Owns DAGRenderer (keeps it alive)
- Owns `viz_input_manager` (VISUALIZATION context)
- Owns VisualizationWindow
- Thread-safe control API using `queue.Queue`:
  - `deploy_pipeline(pipeline_config)` - Queue pipeline swap (thread-safe, non-blocking)
  - `get_state()` - Query current shader, effects, params (thread-safe, returns copy)
  - `start()` - Start render thread (non-blocking, launches daemon thread)
  - `stop()` - Stop render thread (sets flag, waits for thread with timeout)

**VisualizationRunner Structure**:
```python
class VisualizationRunner:
    def __init__(self, width, height, ...):
        """Initialize runner (does NOT create pyglet window yet)"""
        # Store config for thread to use
        self._width = width
        self._height = height
        # ... other config ...
        
        # Thread-safe communication
        self._pipeline_queue = queue.Queue()
        self._stop_flag = threading.Event()
        self._thread = None
        
        # These will be created in visualization thread
        self._renderer = None
        self._viz_window = None
        self._viz_input_manager = None
    
    def start(self):
        """Launch visualization thread (non-blocking)"""
        self._thread = threading.Thread(
            target=self._run_loop,
            name="VisualizationThread",
            daemon=True
        )
        self._thread.start()
    
    def _run_loop(self):
        """Main visualization thread loop - CRITICAL: pyglet window created HERE"""
        # CRITICAL: Create pyglet window IN THIS THREAD
        # This creates the OpenGL context in this thread (avoids macOS constraints)
        self._viz_window = VisualizationWindow(
            width=self._width,
            height=self._height,
            title="Cube Visualization"
        )
        
        # Create renderer (uses OpenGL context from pyglet window)
        self._renderer = DAGRenderer(...)
        
        # Create input manager
        self._viz_input_manager = InputManager(context=VISUALIZATION)
        
        # Register MIDI source (always active, regardless of focus)
        # ... register MIDI ...
        
        # Main render loop
        while not self._stop_flag.is_set():
            # Poll pyglet events
            self._viz_window.poll()
            
            # Update visualization input (keyboard + MIDI)
            self._viz_input_manager.poll()
            
            # Check pipeline deployment queue
            try:
                config = self._pipeline_queue.get_nowait()
                self._deploy_pipeline_internal(config)
            except queue.Empty:
                pass
            
            # Update renderer from input
            # Handle camera, params, effects from viz_input_manager
            
            # Render frame
            self._renderer.render()
            
            # Display to pyglet window
            self._viz_window.display(self._renderer.framebuffer)
            
            # FPS limit
            time.sleep(1.0 / 60.0)  # 60 FPS
        
        # Cleanup (still in visualization thread)
        if self._renderer:
            self._renderer.cleanup()
        if self._viz_window:
            self._viz_window.cleanup()
    
    def deploy_pipeline(self, config):
        """Thread-safe pipeline deployment"""
        self._pipeline_queue.put(config)
    
    def stop(self, timeout=5.0):
        """Graceful shutdown"""
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=timeout)
```

### 4.4 Why This Threading Approach Works

**OpenGL Context Constraints**:
- OpenGL contexts are thread-local (each thread needs its own)
- On macOS, contexts should be created in the thread where they're used
- Contexts cannot be shared simultaneously across threads

**Pygame (Main Thread)**:
- Uses SDL software rendering (no OpenGL)
- No OpenGL context created ✅
- Can safely run in main thread

**Pyglet (Visualization Thread)**:
- Creates OpenGL context automatically when `Window()` is created
- **Critical**: Window must be created IN the visualization thread
- Context is created in the thread that uses it ✅
- Avoids macOS constraints (context created where it's used)

**Result**:
- Main thread: No OpenGL context (pygame only)
- Visualization thread: Own OpenGL context (created in that thread)
- No conflicts, no sharing needed, macOS happy ✅

### 4.5 Controller Integration

- **File**: `src/cube/controller.py`
- Create `visualization_runner = VisualizationRunner(...)` in `__init__`
  - Pass config (width, height, etc.) but DON'T create pyglet window yet
- Call `visualization_runner.start()` to launch thread (non-blocking)
  - Thread creates pyglet window internally (creates OpenGL context in that thread)
- Keep runner alive (don't destroy on menu exit)
- Menu can call `visualization_runner.deploy_pipeline()` to swap shaders (thread-safe queue)
- On application shutdown: `visualization_runner.stop()` (waits for thread with timeout)

## Phase 7: Debug Logging (Thread-Safe)

### 7.1 Thread-Safe Log Capture

- **File**: `src/cube/utils/debug_log.py` (new, based on `cube_v2/ui/debug_log.py`)
- Create `StdoutCapture` class:
  - Thread-safe list for log lines (`log_lines: List[str]`)
  - Thread lock (`log_lock: threading.Lock()`)
  - Captures `print()` statements from ANY thread automatically
  - Stores last N lines (e.g., 1000)
  - Adds thread identifier: `[MAIN]` or `[VIZ]` prefix
  - Adds timestamp for each log line
  - Handles partial lines (buffers until newline)

**Key Insight**: When `sys.stdout` is redirected in the main thread, ALL threads automatically use the same redirected stdout. No special setup needed in other threads!

**StdoutCapture Implementation**:
```python
import sys
import threading
from datetime import datetime
from typing import List

class StdoutCapture:
    """Thread-safe stdout capture with thread identification."""
    
    def __init__(self, log_lines: List[str], log_lock: threading.Lock):
        self.log_lines = log_lines
        self.log_lock = log_lock
        self.original_stdout = sys.stdout
        self.buffer = ""  # Buffer for partial lines
    
    def write(self, text: str):
        """Thread-safe write with thread identification and timestamp."""
        if not text:
            return
        
        if not isinstance(text, str):
            text = str(text)
        
        # Get thread identifier
        thread_name = threading.current_thread().name
        if thread_name == "MainThread":
            prefix = "[MAIN]"
        elif thread_name == "VisualizationThread":
            prefix = "[VIZ]"
        else:
            prefix = f"[{thread_name}]"
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with self.log_lock:
            self.buffer += text
            
            # Process complete lines
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.rstrip('\r\n')
                if line:  # Only add non-empty lines
                    formatted = f"[{timestamp}] {prefix} {line}"
                    self.log_lines.append(formatted)
                    # Keep last 1000 lines
                    if len(self.log_lines) > 1000:
                        self.log_lines.pop(0)
        
        # Also write to original stdout (for terminal/debugging)
        self.original_stdout.write(text)
    
    def flush(self):
        """Flush buffer if it has content."""
        with self.log_lock:
            if self.buffer.strip():
                thread_name = threading.current_thread().name
                if thread_name == "MainThread":
                    prefix = "[MAIN]"
                elif thread_name == "VisualizationThread":
                    prefix = "[VIZ]"
                else:
                    prefix = f"[{thread_name}]"
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                line = self.buffer.rstrip('\r\n')
                if line:
                    formatted = f"[{timestamp}] {prefix} {line}"
                    self.log_lines.append(formatted)
                    if len(self.log_lines) > 1000:
                        self.log_lines.pop(0)
                self.buffer = ""
        
        self.original_stdout.flush()
    
    def isatty(self):
        return False
    
    def writable(self):
        return True
```

### 7.2 Redirect Stdout in Main Thread

- **File**: `src/cube/controller.py`
- In `__init__` or `run()` (BEFORE any threads start):
  - Create shared `log_lines: List[str] = []`
  - Create shared `log_lock: threading.Lock() = threading.Lock()`
  - Create `StdoutCapture(log_lines, log_lock)`
  - Store original: `self.original_stdout = sys.stdout`
  - Redirect: `sys.stdout = stdout_capture`
- **Critical**: Must redirect in main thread BEFORE `visualization_runner.start()` is called
- **How It Works**: When `sys.stdout` is redirected, Python's `print()` function uses the current `sys.stdout` object. Since `sys.stdout` is a module-level variable, ALL threads automatically use the same redirected stdout. No special setup needed in visualization thread!
- All threads' `print()` statements will be captured automatically (both main and visualization threads)

**Initialization Order**:
```python
def __init__(self):
    # 1. Set up debug logging FIRST (before any threads)
    self.log_lines = []
    self.log_lock = threading.Lock()
    self.stdout_capture = StdoutCapture(self.log_lines, self.log_lock)
    self.original_stdout = sys.stdout
    sys.stdout = self.stdout_capture
    
    # 2. Create visualization runner (but don't start thread yet)
    self.visualization_runner = VisualizationRunner(...)
    
    # 3. Create menu window
    self.menu_window = MenuWindow(...)
    
    # 4. Now start visualization thread (stdout already redirected)
    self.visualization_runner.start()
```

### 7.3 Thread Identification in Logs

- **File**: `src/cube/utils/debug_log.py`
- `StdoutCapture.write()` automatically detects thread:
  - Uses `threading.current_thread().name` to identify thread
  - Maps `"MainThread"` → `[MAIN]`
  - Maps `"VisualizationThread"` → `[VIZ]`
  - Other threads → `[ThreadName]`
- Format: `[HH:MM:SS] [THREAD] message` (with timestamp)
- Example outputs:
  - `[14:23:45] [MAIN] Menu opened`
  - `[14:23:46] [VIZ] Rendering frame 1234`
  - `[14:23:47] [VIZ] Pipeline deployed: ascii.glsl`
  - `[14:23:48] [MAIN] User selected shader: skyline.glsl`

**Thread Name Setup**:
- Main thread: Default name is `"MainThread"` (Python default)
- Visualization thread: Explicitly set name in `threading.Thread(name="VisualizationThread")`
- Other threads: Use their actual thread names

### 7.4 Display Logs in Menu

- **File**: `src/cube/menu/debug_log_view.py` (new, or integrate into existing menu)
- Menu can display log lines from shared `log_lines`
- Read with lock: `with log_lock: lines = log_lines[-100:]` (last 100 lines)
- Render in menu overlay or separate debug pane
- Auto-scroll to latest logs
- Filter by thread if needed: `[MAIN]` vs `[VIZ]`
- Color-code by thread (optional): MAIN in one color, VIZ in another

**Menu Log Display**:
```python
def render_debug_logs(self, menu_window, log_lines, log_lock):
    """Render debug logs in menu overlay"""
    # Read logs with lock (make copy to minimize lock time)
    with log_lock:
        recent_logs = log_lines[-100:].copy()  # Last 100 lines
    
    # Render logs in menu UI
    # - Auto-scroll to bottom
    # - Optionally filter by thread prefix (e.g., show only [VIZ] logs)
    # - Color-code by thread prefix
    # - Truncate long lines for display
    for i, log_line in enumerate(recent_logs):
        # Parse thread prefix for color-coding
        if "[MAIN]" in log_line:
            color = MENU_COLOR
        elif "[VIZ]" in log_line:
            color = VIZ_COLOR
        else:
            color = DEFAULT_COLOR
        
        # Render line (truncate if needed)
        menu_window.render_text(log_line[:80], y=i, color=color)
```

**Integration Points**:
- Can be rendered as overlay on menu (toggle with debug key)
- Can be separate menu state/screen
- Can be side panel in pipeline builder

### 7.5 Logging from All Threads

**Main Thread Logging**:
- **File**: `src/cube/controller.py`, `src/cube/menu/*.py`
- Use `print()` statements normally
- Automatically captured and prefixed with `[MAIN]`
- Examples:
  - `print("Menu opened")` → `[14:23:45] [MAIN] Menu opened`
  - `print(f"Selected shader: {shader_path}")` → `[14:23:46] [MAIN] Selected shader: ascii.glsl`

**Visualization Thread Logging**:
- **File**: `src/cube/render/visualization_runner.py`, `src/cube/render/dag_renderer.py`
- Use `print()` statements normally
- Automatically captured and prefixed with `[VIZ]`
- Examples:
  - `print("Rendering frame 1234")` → `[14:23:47] [VIZ] Rendering frame 1234`
  - `print(f"Pipeline deployed: {config.source.shader_path}")` → `[14:23:48] [VIZ] Pipeline deployed: ascii.glsl`
  - `print(f"OpenGL error: {error}")` → `[14:23:49] [VIZ] OpenGL error: ...`

**Other Threads** (if any):
- Any background threads (e.g., shader generation, MIDI processing)
- Use `print()` statements normally
- Automatically captured and prefixed with thread name
- Example: `[14:23:50] [ShaderAgent] Generated shader: test.glsl`

**No Special Setup Required**:
- Once `sys.stdout` is redirected in main thread, ALL threads automatically use it
- No need to pass log_lines or log_lock to other threads
- No need to configure logging in visualization thread
- Just use `print()` statements everywhere!

**Log Flow**:
1. **Main thread**: `print("Menu opened")` 
   → `StdoutCapture.write()` called (in main thread)
   → Detects thread name: `"MainThread"`
   → Formats: `[14:23:45] [MAIN] Menu opened`
   → Appends to `log_lines` (with lock)
   → Also writes to original stdout (terminal)

2. **Visualization thread**: `print("Rendering frame")`
   → `StdoutCapture.write()` called (in visualization thread)
   → Detects thread name: `"VisualizationThread"`
   → Formats: `[14:23:46] [VIZ] Rendering frame`
   → Appends to `log_lines` (with lock)
   → Also writes to original stdout (terminal)

3. **Menu reads logs**: 
   → `with log_lock: recent_logs = log_lines[-100:].copy()`
   → Renders in menu UI overlay
   → Both threads' logs appear in real-time

**Thread Safety**:
- `StdoutCapture.write()` uses `log_lock` to protect `log_lines` list
- Multiple threads can call `write()` simultaneously (lock serializes access)
- Menu reads logs with lock (makes copy to minimize lock time)
- No race conditions or data corruption

### 7.6 Summary: Debug Logging Architecture

**Key Points**:
1. **Single Redirect**: `sys.stdout` is redirected ONCE in main thread (before any threads start)
2. **Automatic Capture**: ALL threads automatically use the redirected stdout (no special setup needed)
3. **Thread Identification**: Each log line is tagged with thread name (`[MAIN]`, `[VIZ]`, etc.)
4. **Thread-Safe**: Lock protects shared `log_lines` list from concurrent access
5. **Real-Time Display**: Menu reads logs and displays them in UI overlay
6. **Terminal Fallback**: Logs also go to original stdout (terminal) for debugging

**What Each Thread Does**:
- **Main thread**: Redirects stdout, reads logs for display, uses `print()` normally
- **Visualization thread**: Uses `print()` normally (no special setup)
- **Other threads**: Use `print()` normally (no special setup)

**What Happens Automatically**:
- All `print()` calls from any thread → captured → tagged with thread name → stored in shared list → displayed in menu
- No need to pass log_lines or log_lock to other threads
- No need to configure logging in visualization thread
- Just use `print()` everywhere!

## Phase 5: Pipeline Builder UI

### 5.1 Create PipelineBuilderState

- **File**: `src/cube/menu/pipeline_builder.py` (new)
- MenuState for building pipelines
- UI elements:
  - Source shader selector
  - Effect chain builder (add/remove/reorder effects)
  - Parameter presets
  - Deploy button

### 5.2 Pipeline Configuration

- **File**: `src/cube/render/pipeline_config.py` (new)
- JSON format:
```json
{
  "source": {
    "shader_path": "shaders/effects/ascii.glsl",
    "pixel_mapper": "surface"
  },
  "effects": [
    {"action": "TOGGLE_KALEIDOSCOPE", "enabled": true},
    {"action": "TOGGLE_BLOOM", "enabled": false}
  ],
  "params": [0.5, 0.3, 0.0, 0.0, ...]  // param0-7 values
}
```


### 5.3 Pipeline Manager

- **File**: `src/cube/render/pipeline_manager.py` (new)
- `deploy_pipeline(visualization_runner, config)`:

  1. Load shader: `renderer.load_shader(config.source.shader_path)`
  2. Enable/disable effects: `effect_manager` toggle effects
  3. Set parameters: `param_source._cached_params` (if needed)
  4. Rebuild effects: `effect_manager.rebuild_active()`

## Phase 6: Controller Refactoring

### 6.1 Main Loop Changes

- **File**: `src/cube/controller.py`
- Menu loop (main thread):
  - Poll `menu_window` events
  - Update `menu_input_manager` (only if menu focused)
  - Handle menu navigation/actions
  - Render menu to `menu_window`
  - Read and display debug logs from shared `log_lines`

- Visualization loop (separate thread):
  - Handled by VisualizationRunner
  - Runs independently

### 6.2 Keep Renderer Alive

- **File**: `src/cube/controller.py`
- Don't call `renderer.cleanup()` when exiting visualization
- VisualizationRunner owns renderer
- Only cleanup on application shutdown

## Implementation Order

1. **Phase 1**: Remove DisplayMode abstraction
2. **Phase 2**: Create MenuWindow and VisualizationWindow
3. **Phase 7**: Set up thread-safe debug logging (do this early!)
4. **Phase 3**: Implement input routing (keyboard focus, MIDI always to viz)
5. **Phase 4**: Create VisualizationRunner with separate thread
6. **Phase 6**: Refactor controller main loop (menu stays in main thread)
7. **Phase 5**: Build pipeline builder UI (later)

## Key Files to Create

1. `src/cube/display/menu_window.py` - Pygame window wrapper
2. `src/cube/display/visualization_window.py` - Pyglet window wrapper
3. `src/cube/utils/debug_log.py` - Thread-safe stdout capture
4. `src/cube/menu/debug_log_view.py` - Debug log display in menu
5. `src/cube/render/visualization_runner.py` - Independent render thread
6. `src/cube/menu/pipeline_builder.py` - Pipeline builder UI (later)
7. `src/cube/render/pipeline_config.py` - Pipeline config format (later)
8. `src/cube/render/pipeline_manager.py` - Pipeline deployment (later)

## Key Files to Modify

1. `src/cube/controller.py` - Separate windows, input routing, keep renderer alive, debug log setup
2. `src/cube/render/dag_renderer.py` - No changes (already supports shader swapping)
3. `src/cube/render/effect_manager.py` - No changes (already supports rebuilding)

## Files to Remove

1. `src/cube/display/display_mode.py`
2. `src/cube/display/multi_window_mode.py`
3. `src/cube/display/multi_window_pygame.py`

## Benefits

- ✅ Simple, direct approach (no abstraction layer)
- ✅ Parameters persist (renderer stays alive)
- ✅ Effects persist (effect_manager stays alive)
- ✅ Build next pipeline while current runs
- ✅ Clear input routing (focus-based keyboard, MIDI to viz)
- ✅ Independent windows (pygame menu, pyglet visualization)
- ✅ Thread-safe debug logging (both threads visible in menu)
- ✅ Menu stays in main thread (simpler pygame management)
- ✅ Visualization in daemon thread (independent, non-blocking)

