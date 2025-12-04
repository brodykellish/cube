"""
AI Prompt Menu State - Natural language shader generation interface.

Provides an interactive prompt where users can describe shaders they want,
and Claude Code generates them on demand.
"""

from pathlib import Path
from typing import Optional, List
import numpy as np
import threading

from .menu_states import MenuState, ShaderBrowser
from .menu_context import MenuContext
from .text_box import TextBox, wrap_text
from .actions import MenuAction, LaunchVisualizationAction, ShaderSelectionAction
from cube.ai import ShaderAgent, ShaderGenerationResult
from cube.render import UnifiedRenderer, SurfacePixelMapper
from cube.shader import SphericalCamera


class PromptMenuState(MenuState):
    """
    Menu state for AI-powered shader generation via prompts.

    Flow:
    1. User enters natural language description
    2. System generates shader via Claude Code
    3. Shader is automatically displayed
    4. User can refine or create new shader
    """

    def __init__(self, width: int, height: int, shaders_dir: Path):
        """
        Initialize prompt menu.

        Args:
            width: Display width
            height: Display height
            shaders_dir: Root shaders directory
        """
        super().__init__('prompt')
        self.width = width
        self.height = height
        self.shaders_dir = shaders_dir

        # Create shader agent with examples root
        # Note: shaders_dir is already the root, we write to 'generated' subdirectory
        generated_dir = shaders_dir / 'generated'
        generated_dir.mkdir(parents=True, exist_ok=True)

        # Create a minimal validation renderer for shader compilation testing
        # This is only used for validation, not actual rendering
        try:
            validation_mapper = SurfacePixelMapper(
                width=64,  # Minimal size
                height=64,
                camera=SphericalCamera()
            )
            self.validation_renderer = UnifiedRenderer(
                pixel_mapper=validation_mapper,
                settings={},
                uniform_sources=[]
            )
            print("✓ Created validation renderer for shader testing")
        except Exception as e:
            print(f"⚠ Could not create validation renderer: {e}")
            print("  Shader validation will be disabled")
            self.validation_renderer = None

        self.agent = ShaderAgent(
            shaders_dir=generated_dir,  # Direct path, no extra nesting
            examples_root=shaders_dir,  # Root directory with primitives/ and graphics/
            validation_renderer=self.validation_renderer  # Pass renderer for validation
        )

        # Text box for conversation history
        # Use 1 character width (4 pixels) padding on each edge
        char_width = 4  # Character width at scale=1 (3 pixels + 1 spacing)
        text_box_height = height - 80  # Leave room for input and status
        self.text_box = TextBox(
            x=char_width, y=40, width=width - (char_width * 2), height=text_box_height,
            fg_color=(200, 200, 200), bg_color=(00, 00, 00)
        )

        # User input buffer and cursor
        self.input_buffer = ""
        self.cursor_pos = 0  # Position in buffer (0 = before first char, len = after last char)
        self.cursor_visible = True
        self.cursor_blink_time = 0
        self.scroll_offset = 0  # Horizontal scroll offset for long input
        self.loading_animation_time = 0  # Timer for loading ellipsis animation

        # State
        self.is_generating = False
        self.active_command: Optional[str] = None  # Current command mode (None, 'shader', etc.)
        self.status_message = "Type /shader to enter shader generation mode"

        # Track current shader and iteration count
        self.current_shader_name: Optional[str] = None
        self.current_shader_path: Optional[Path] = None  # Full path for editing
        self.iteration_count = 0
        self.last_error: Optional[str] = None  # Store visualization errors for feedback
        self.editing_mode = False  # True when editing existing shader vs creating new

        # Async generation state
        self.generation_thread: Optional[threading.Thread] = None
        self.generation_result: Optional[ShaderGenerationResult] = None
        self.generation_complete = False
        self.pending_action: Optional[MenuAction] = None

        # Shader browser for /list command (no pixel mapper selection needed)
        self.shader_browser = ShaderBrowser(
            pixel_mapper='surface',  # Default, not used for editing
            include_pixel_mapper=False
        )
        self.browser_active = False  # True when showing shader browser

        # Available commands and their agents
        self.commands = {
            'shader': {
                'agent': self.agent,
                'description': 'Generate GLSL shaders from natural language'
            },
            'list': {
                'agent': None,
                'description': 'Browse and select existing shaders to edit'
            },
            'vis': {
                'agent': None,
                'description': 'Visualize current shader'
            }
        }

        # Initial welcome message
        welcome = (
            "AI COMMAND PROMPT\n\n"
            "Available commands:\n"
            "  /shader - Generate new shaders\n"
            "  /list - Browse and edit existing shaders\n"
            "  /vis - Visualize current shader\n\n"
            "Usage:\n"
            "  1. Type /shader to create new shaders\n"
            "  2. Type /list to load existing shader for editing\n"
            "  3. Type /vis to visualize the current shader\n"
            "  4. Press ESC to exit command mode\n\n"
            "In normal mode, messages are echoed back for UI testing."
        )
        self.text_box.set_text(welcome)

    def enter_editing_mode(self, shader_path: Path):
        """
        Enter editing mode for a specific shader.

        This should be called when a shader is selected from the browser
        or after visualizing a newly generated shader.

        Args:
            shader_path: Path to shader file to edit
        """
        self.editing_mode = True
        self.current_shader_name = shader_path.name
        self.current_shader_path = shader_path
        self.active_command = 'shader'
        self.iteration_count = 0  # Reset iteration count for new editing session

        self.text_box.append_text(f"cube: [Editing {shader_path.name}]")
        self.text_box.append_text(f"cube: Describe modifications or press ESC to exit.")
        self.status_message = f"Editing {shader_path.name}"

    def set_shader_error(self, error_message: str):
        """
        Set error feedback from visualization system.

        This should be called when a shader fails to compile or render.
        The error will be fed back to the agent on the next generation attempt.

        Args:
            error_message: Error log from shader compilation/rendering

        Example:
            menu_state.set_shader_error("ERROR: undefined variable 'iCamerPos'")
        """
        self.last_error = error_message
        self.text_box.append_text(f"cube: ERROR - Shader failed to render")
        self.text_box.append_text(f"cube: {error_message[:200]}")  # Show truncated error
        self.status_message = "Shader error captured - will auto-fix on retry"

    def handle_paste(self, text: str):
        """
        Handle pasted text (Cmd+V / Ctrl+V).

        Args:
            text: Pasted text from clipboard
        """
        # Don't accept paste while generating or browser active
        if self.is_generating or self.browser_active:
            return

        # Insert pasted text at cursor position
        # Replace newlines with spaces (single-line input)
        text = text.replace('\n', ' ').replace('\r', ' ')

        self.input_buffer = self.input_buffer[:self.cursor_pos] + text + self.input_buffer[self.cursor_pos:]
        self.cursor_pos += len(text)

        # Reset cursor blink
        self.cursor_visible = True
        self.cursor_blink_time = 0

    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        """
        Handle keyboard input.

        Args:
            key: Key that was pressed
            context: Menu context

        Returns:
            MenuAction if action should be taken, None otherwise
        """
        # If browser is active, delegate to it
        if self.browser_active:
            action = self.shader_browser.handle_input(key, context)

            if isinstance(action, ShaderSelectionAction):
                # User selected a shader - enter editing mode
                self.browser_active = False
                self.enter_editing_mode(action.shader_path)
                return None
            elif action:
                # Other actions (BackAction, etc.) - close browser
                self.browser_active = False
                return None

            return None

        # Don't accept input while generating
        if self.is_generating:
            return None

        # Handle text input
        if key == 'enter':
            return self._submit_prompt()
        elif key == 'escape':
            if self.active_command:
                # Exit command mode back to normal prompt mode
                self._exit_command_mode()
            else:
                # Return to main menu
                from .actions import NavigateAction
                return NavigateAction('main')
        elif key == 'ctrl-c':
            # Clear input buffer and reset cursor
            self.input_buffer = ""
            self.cursor_pos = 0
            self.scroll_offset = 0
        elif key == 'left':
            # Move cursor left
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                # Reset cursor blink on movement
                self.cursor_visible = True
                self.cursor_blink_time = 0
        elif key == 'right':
            # Move cursor right
            if self.cursor_pos < len(self.input_buffer):
                self.cursor_pos += 1
                # Reset cursor blink on movement
                self.cursor_visible = True
                self.cursor_blink_time = 0
        elif key == 'backspace':
            # Delete character before cursor
            if self.cursor_pos > 0:
                self.input_buffer = self.input_buffer[:self.cursor_pos-1] + self.input_buffer[self.cursor_pos:]
                self.cursor_pos -= 1
        elif key == 'delete':
            # Delete character at cursor
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = self.input_buffer[:self.cursor_pos] + self.input_buffer[self.cursor_pos+1:]
        elif key == 'space':
            # Insert space character (SSH keyboard returns 'space' as the key name)
            self.input_buffer = self.input_buffer[:self.cursor_pos] + ' ' + self.input_buffer[self.cursor_pos:]
            self.cursor_pos += 1
            # Reset cursor blink on typing
            self.cursor_visible = True
            self.cursor_blink_time = 0
        elif len(key) == 1 and key.isprintable():
            # Insert character at cursor position
            self.input_buffer = self.input_buffer[:self.cursor_pos] + key + self.input_buffer[self.cursor_pos:]
            self.cursor_pos += 1
            # Reset cursor blink on typing
            self.cursor_visible = True
            self.cursor_blink_time = 0

        return None

    def _submit_prompt(self) -> Optional[MenuAction]:
        """
        Submit user prompt - routes to command agent or echoes back.

        Returns:
            MenuAction if action should be taken (e.g., launch visualization)
        """
        if not self.input_buffer.strip():
            return None

        user_prompt = self.input_buffer.strip()
        self.input_buffer = ""
        self.cursor_pos = 0
        self.scroll_offset = 0

        # Check if this is a command invocation
        if user_prompt.startswith('/'):
            return self._handle_command(user_prompt)

        # Update display
        self.text_box.append_text(f"user: {user_prompt}")

        # Route to active command or echo back
        if self.active_command:
            print(f"cube: Routing to command: {self.active_command}")
            return self._route_to_command(user_prompt)
        else:
            # Normal mode - just echo back
            self.text_box.append_text(f"cube: {user_prompt}")
            self.status_message = "Message echoed (normal mode)"

        return None

    def _handle_command(self, command_input: str) -> Optional[MenuAction]:
        """
        Handle command invocation (e.g., /shader).

        Args:
            command_input: Full command string including /

        Returns:
            MenuAction if needed
        """
        # Parse command
        parts = command_input[1:].split()  # Remove / and split
        if not parts:
            return None

        command_name = parts[0].lower()

        # Check if command exists
        if command_name not in self.commands:
            self.text_box.append_text(f"user: {command_input}")
            self.text_box.append_text(f"cube: ERROR - Unknown command '/{command_name}'")
            self.text_box.append_text(f"cube: Available commands: {', '.join('/' + c for c in self.commands.keys())}")
            self.status_message = f"Unknown command: /{command_name}"
            return None

        # Handle special commands
        if command_name == 'list':
            # Show shader browser for selecting shader to edit
            self.browser_active = True
            self.text_box.append_text(f"cube: [Browse shaders to edit]")
            self.status_message = "Browse shaders - Select one to edit"
            return None

        elif command_name == 'vis':
            # Visualize current shader
            if self.current_shader_path:
                self.text_box.append_text(f"cube: Visualizing {self.current_shader_name}...")
                return LaunchVisualizationAction(
                    shader_path=self.current_shader_path,
                    pixel_mapper='surface'  # Default to surface
                )
            else:
                self.text_box.append_text(f"user: {command_input}")
                self.text_box.append_text(f"cube: ERROR - No shader loaded")
                self.text_box.append_text(f"cube: Use /shader to create or /list to load a shader first")
                self.status_message = "No shader loaded"
                return None

        # Enter command mode
        self.active_command = command_name
        command_info = self.commands[command_name]

        self.text_box.append_text(f"cube: [Entered /{command_name} mode]")
        self.text_box.append_text(f"cube: {command_info['description']}")
        self.text_box.append_text("cube: Type your request or press ESC to exit.")

        self.status_message = f"/{command_name} mode active - Press ESC to exit"

        return None

    def _exit_command_mode(self):
        """Exit the current command mode."""
        if self.active_command:
            self.text_box.append_text(f"cube: [Exited /{self.active_command} mode]")
            self.active_command = None
            # Exit editing mode when exiting command mode
            if self.editing_mode:
                self.editing_mode = False
                self.current_shader_name = None
                self.current_shader_path = None
                self.iteration_count = 0
            self.status_message = "Command mode exited. Type /shader to re-enter."

    def _route_to_command(self, user_prompt: str) -> Optional[MenuAction]:
        """
        Route prompt to the active command's agent.

        Args:
            user_prompt: User's input

        Returns:
            MenuAction if needed
        """
        if self.active_command == 'shader':
            return self._handle_shader_generation(user_prompt)
        elif self.active_command == 'list':
            # /list shows shader browser - return navigation action
            from .actions import NavigateAction
            return NavigateAction('visualize')

        # Unknown command (shouldn't happen)
        self.text_box.append_text(f"cube: ERROR - No handler for command '{self.active_command}'")
        return None

    def _handle_shader_generation(self, user_prompt: str) -> Optional[MenuAction]:
        """
        Handle shader generation request (starts async generation).

        Args:
            user_prompt: User's shader description

        Returns:
            None (result will be processed when thread completes)
        """
        print(f"cube: Handling shader generation request: {user_prompt}")

        # Show loading state immediately
        self.text_box.append_text(f"cube: ...")  # Will be animated in update()
        self.status_message = "⏳ Generating shader..."
        self.is_generating = True
        self.generation_complete = False
        self.generation_result = None
        self.pending_action = None
        self.loading_animation_time = 0  # Reset animation timer

        # Start generation in background thread
        self.generation_thread = threading.Thread(
            target=self._generate_shader_async,
            args=(user_prompt,),
            daemon=True
        )
        self.generation_thread.start()

        return None

    def _generate_shader_async(self, user_prompt: str):
        """
        Background thread worker for shader generation.

        Args:
            user_prompt: User's shader description
        """
        try:
            # Determine if we're editing existing shader or creating new
            if self.editing_mode and self.current_shader_path:
                # Editing mode - modify existing shader
                print(f"cube: Editing existing shader: {self.current_shader_name}")
                # Read current shader for context
                try:
                    current_code = self.current_shader_path.read_text()
                    edit_prompt = f"I'm editing the shader '{self.current_shader_name}'.\n\nCurrent code:\n```glsl\n{current_code}\n```\n\nModification request: {user_prompt}"
                    print(f"cube: Edit prompt: {edit_prompt}")
                except Exception:
                    edit_prompt = f"Modify the shader '{self.current_shader_name}': {user_prompt}"

                # For editing, use direct generate_shader with editing prompt
                # The shader already compiled before, we're just modifying it
                result = self.commands['shader']['agent'].generate_shader_with_validation(
                    edit_prompt,
                    "editing"
                )

                # If successful, overwrite the existing shader
                if result.success and result.shader_path:
                    # Move generated shader to replace the current one
                    try:
                        # Read content BEFORE unlinking
                        generated_content = result.shader_path.read_text()
                        # Write to current shader
                        self.current_shader_path.write_text(generated_content)
                        # Remove temp generated file
                        result.shader_path.unlink()
                        # Update result to point to the actual file
                        result.shader_path = self.current_shader_path
                    except Exception as e:
                        print(f"Warning: Could not replace shader: {e}")
            else:
                # Creation mode - generate new shader WITH VALIDATION
                # This will automatically detect and retry on compilation errors
                result = self.commands['shader']['agent'].generate_shader_with_validation(
                    user_prompt,
                    "generation"
                )

            # Clear error after using it
            self.last_error = None

            # Store result for main thread to process
            self.generation_result = result
            self.generation_complete = True

        except Exception as e:
            print(f"Error in shader generation thread: {e}")
            import traceback
            traceback.print_exc()
            # Create error result
            self.generation_result = ShaderGenerationResult(
                success=False,
                error=f"Generation exception: {str(e)}"
            )
            self.generation_complete = True

    def render(self, renderer, context: MenuContext):
        """
        Render prompt interface.

        Args:
            renderer: MenuRenderer to draw with
            context: Menu context with display info
        """
        # If browser is active, render it instead
        if self.browser_active:
            self.shader_browser.render(renderer, context)
            return

        # Clear background - black
        renderer.clear((0, 0, 0))

        # Minimal header - show mode and shader info
        header_y = 5
        text_box_y_start = 5

        # Show active command mode and editing state
        if self.active_command:
            if self.editing_mode and self.current_shader_name:
                # Show editing mode with shader name
                max_filename_chars = 35
                display_name = self.current_shader_name
                if len(display_name) > max_filename_chars:
                    display_name = "..." + display_name[-(max_filename_chars-3):]

                mode_text = f"EDIT: {display_name} (Iter {self.iteration_count})"
                renderer.draw_text(mode_text, 5, header_y, color=(255, 200, 100), scale=1)  # Orange for editing
            else:
                # Show command mode
                mode_text = f"MODE: /{self.active_command}"
                renderer.draw_text(mode_text, 5, header_y, color=(100, 200, 100), scale=1)  # Green for create
            text_box_y_start = header_y + 15

        # Calculate input area position (bottom of screen)
        input_y = context.height - 15  # Reduced from 30
        input_height = 12  # Reduced from 25 - single row

        # Update text box position and size
        # Use 1 character width (4 pixels) padding on each edge
        char_width = 4  # Character width at scale=1 (3 pixels + 1 spacing)
        self.text_box.update_dimensions(
            x=char_width,
            y=text_box_y_start,
            width=context.width - (char_width * 2),
            height=input_y - text_box_y_start - 5
        )

        # Draw 1px border around text box
        border_color = (60, 60, 60)  # Dark gray border
        x, y, w, h = self.text_box.x, self.text_box.y, self.text_box.width, self.text_box.height
        # Top border
        renderer.framebuffer[y:y+1, x:x+w] = border_color
        # Bottom border
        renderer.framebuffer[y+h-1:y+h, x:x+w] = border_color
        # Left border
        renderer.framebuffer[y:y+h, x:x+1] = border_color
        # Right border
        renderer.framebuffer[y:y+h, x+w-1:x+w] = border_color

        # Render text box (conversation history)
        self.text_box.render(renderer.framebuffer)

        # Render input area with cursor navigation
        input_text_y = input_y + 1  # Minimal padding
        input_text_x = char_width

        # Calculate visible width for input
        available_width = context.width - (char_width * 2)
        prompt_prefix = "> "
        prefix_width = len(prompt_prefix)
        max_visible_chars = (available_width // char_width) - prefix_width

        # Auto-scroll to keep cursor visible with padding
        # Trigger scroll 1 character before edge for better UX
        scroll_padding = 1

        if self.cursor_pos < self.scroll_offset + scroll_padding:
            # Cursor moved left near edge, scroll left
            self.scroll_offset = max(0, self.cursor_pos - scroll_padding)
        elif self.cursor_pos >= self.scroll_offset + max_visible_chars - scroll_padding:
            # Cursor moved right near edge, scroll right
            self.scroll_offset = self.cursor_pos - max_visible_chars + scroll_padding + 1

        # Clamp scroll offset
        max_scroll = max(0, len(self.input_buffer) - max_visible_chars)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

        # Extract visible portion of text
        visible_start = self.scroll_offset
        visible_end = self.scroll_offset + max_visible_chars
        visible_text = self.input_buffer[visible_start:visible_end]

        # Calculate cursor position within visible window
        cursor_in_visible = self.cursor_pos - self.scroll_offset

        # Build display text with cursor or loading indicator
        if self.is_generating:
            # Show loading animation - no cursor while generating
            display_text = visible_text
        elif self.cursor_visible:
            # Insert cursor at correct position
            display_text = visible_text[:cursor_in_visible] + "_" + visible_text[cursor_in_visible:]
        else:
            display_text = visible_text

        # Add scroll indicators
        left_indicator = "<" if self.scroll_offset > 0 else ""
        right_indicator = ">" if visible_end < len(self.input_buffer) else ""

        # Render input line with color coding
        # Left indicator in white
        current_x = input_text_x
        if left_indicator:
            renderer.draw_text(left_indicator, current_x, input_text_y, color=(200, 200, 200), scale=1)
            current_x += len(left_indicator) * char_width

        # Prompt prefix "user: " in red
        renderer.draw_text(prompt_prefix, current_x, input_text_y, color=(200, 200, 200), scale=1)
        current_x += len(prompt_prefix) * char_width

        # User input text in white
        if display_text:
            renderer.draw_text(display_text, current_x, input_text_y, color=(200, 200, 200), scale=1)
            current_x += len(display_text) * char_width

        # Right indicator in white
        if right_indicator:
            renderer.draw_text(right_indicator, current_x, input_text_y, color=(200, 200, 200), scale=1)

    def update(self, dt: float) -> Optional[MenuAction]:
        """
        Update prompt state (cursor blinking, loading animation, async results).

        Args:
            dt: Delta time since last update

        Returns:
            MenuAction if generation completed and visualization should launch
        """
        # Cursor blinking
        self.cursor_blink_time += dt
        if self.cursor_blink_time >= 0.5:
            self.cursor_visible = not self.cursor_visible
            self.cursor_blink_time = 0

        # Animate loading ellipsis at 1 FPS (once per second)
        if self.is_generating and self.text_box.lines:
            self.loading_animation_time += dt
            if self.loading_animation_time >= 1.0:  # Update every 1 second
                self.loading_animation_time = 0
                # Find the loading message
                for i in range(len(self.text_box.lines) - 1, -1, -1):
                    if self.text_box.lines[i].startswith("cube: ."):
                        # Cycle through . .. ... ....
                        current = self.text_box.lines[i]
                        dots = current.count('.')
                        if dots >= 4:
                            self.text_box.lines[i] = "cube: ."
                        else:
                            self.text_box.lines[i] = "cube: " + "." * (dots + 1)
                        break

        # Check for async generation completion
        if self.generation_complete and self.generation_result:
            result = self.generation_result

            # Reset generation state
            self.is_generating = False
            self.generation_complete = False
            self.generation_result = None

            # Remove loading message
            if self.text_box.lines and self.text_box.lines[-1].startswith("cube: ."):
                self.text_box.lines = self.text_box.lines[:-1]

            # Process result
            if result.success and result.shader_path:
                # Update tracking
                self.current_shader_name = result.shader_path.name
                self.current_shader_path = result.shader_path
                self.iteration_count += 1
                self.editing_mode = True  # Enter editing mode after first generation

                self.text_box.append_text(f"cube: Created shader: {result.shader_path.name}")
                self.text_box.append_text(f"cube: Launching visualization...")
                self.text_box.append_text(f"cube: Press ESC to return for refinements.")
                self.status_message = f"Iteration {self.iteration_count} - Shader generated!"

                # Return launch action
                return LaunchVisualizationAction(
                    shader_path=result.shader_path,
                    pixel_mapper='surface'  # Default to surface mode
                )
            else:
                # Generation failed
                self.text_box.append_text(f"cube: ERROR - {result.error}")
                if result.log:
                    self.text_box.append_text(f"cube: {result.log[:200]}")  # Truncate long logs
                self.status_message = "Generation failed. Try again."

        return None


class PromptAction(MenuAction):
    """Action to enter prompt interface."""

    def __init__(self):
        """Initialize prompt action."""
        pass

    def __repr__(self):
        return "PromptAction()"
