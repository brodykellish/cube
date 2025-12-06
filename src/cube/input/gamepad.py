"""
Xbox Controller Input for Camera Control

Supports original Xbox controllers (and most USB gamepads) via pygame.joystick.
Maps analog sticks to camera rotation and zoom.
"""

import time
from typing import Optional, Dict, Any


class GamepadCameraInput:
    """
    Xbox controller input for smooth camera control.

    Stick Mapping (Original Xbox Layout):
    - Left Stick X/Y: Yaw (horizontal) / Pitch (vertical) rotation
    - Right Stick X/Y: Roll / Zoom
    - Triggers: Fine zoom control (optional)
    - D-Pad: Discrete camera movements

    Compatible with pygame joystick interface.
    """

    def __init__(self, pygame_module, joystick_index: int = 0):
        """
        Initialize gamepad camera input.

        Args:
            pygame_module: The pygame module (passed to avoid import issues)
            joystick_index: Joystick device index (default: 0 for first controller)
        """
        self.pygame = pygame_module
        self.joystick = None
        self.joystick_index = joystick_index

        # Camera input state (matches CameraUniformSource expectations)
        self.input_state = {
            'left': 0.0,
            'right': 0.0,
            'up': 0.0,
            'down': 0.0,
            'forward': 0.0,
            'backward': 0.0,
        }

        self.shift_pressed = False  # Simulated shift for zoom mode

        # Deadzone to prevent stick drift
        self.deadzone = 0.15

        # Stick sensitivity
        self.rotation_sensitivity = 1.5
        self.zoom_sensitivity = 1.0

        # Initialize joystick
        self._init_joystick()

    def _init_joystick(self):
        """Initialize pygame joystick."""
        try:
            # Initialize pygame joystick subsystem
            self.pygame.joystick.init()

            num_joysticks = self.pygame.joystick.get_count()
            if num_joysticks == 0:
                print("Warning: No gamepad/joystick detected")
                return

            # Open the specified joystick
            self.joystick = self.pygame.joystick.Joystick(self.joystick_index)
            self.joystick.init()

            print(f"✓ Gamepad connected: {self.joystick.get_name()}")
            print(f"  Axes: {self.joystick.get_numaxes()}")
            print(f"  Buttons: {self.joystick.get_numbuttons()}")
            print(f"  Hats: {self.joystick.get_numhats()}")

        except Exception as e:
            print(f"Warning: Could not initialize gamepad: {e}")
            self.joystick = None

    def _apply_deadzone(self, value: float) -> float:
        """
        Apply circular deadzone to analog stick value.

        Args:
            value: Raw stick value (-1.0 to 1.0)

        Returns:
            Adjusted value with deadzone applied
        """
        if abs(value) < self.deadzone:
            return 0.0

        # Scale value to account for deadzone
        # Map from [deadzone, 1.0] to [0.0, 1.0]
        sign = 1.0 if value > 0 else -1.0
        adjusted = (abs(value) - self.deadzone) / (1.0 - self.deadzone)
        return sign * adjusted

    def poll(self) -> Dict[str, float]:
        """
        Poll gamepad for current state.

        Returns:
            Dictionary with camera input state
        """
        if not self.joystick:
            return self.input_state

        try:
            # Left stick (axis 0=X, axis 1=Y)
            # Xbox original: Axis 0 = Left X, Axis 1 = Left Y
            left_x = self.joystick.get_axis(0)
            left_y = self.joystick.get_axis(1)

            # Apply deadzone
            left_x = self._apply_deadzone(left_x)
            left_y = self._apply_deadzone(left_y)

            # Map left stick to yaw/pitch
            # X axis: -1.0 (left) to 1.0 (right) → yaw
            # Y axis: -1.0 (up) to 1.0 (down) → pitch (inverted for natural control)
            yaw_input = left_x * self.rotation_sensitivity
            pitch_input = -left_y * self.rotation_sensitivity  # Invert Y

            # Map to camera input state
            if yaw_input > 0:
                self.input_state['right'] = yaw_input
                self.input_state['left'] = 0.0
            else:
                self.input_state['left'] = -yaw_input
                self.input_state['right'] = 0.0

            if pitch_input > 0:
                self.input_state['up'] = pitch_input
                self.input_state['down'] = 0.0
            else:
                self.input_state['down'] = -pitch_input
                self.input_state['up'] = 0.0

            # Right stick (axis 2=X, axis 3=Y) - for zoom and roll
            # Xbox original: Axis 2 = Right X, Axis 3 = Right Y
            if self.joystick.get_numaxes() >= 4:
                right_x = self.joystick.get_axis(2)
                right_y = self.joystick.get_axis(3)

                # Apply deadzone
                right_x = self._apply_deadzone(right_x)
                right_y = self._apply_deadzone(right_y)

                # Right stick Y controls zoom (inverted)
                zoom_input = -right_y * self.zoom_sensitivity

                if zoom_input > 0:
                    self.input_state['forward'] = zoom_input
                    self.input_state['backward'] = 0.0
                else:
                    self.input_state['backward'] = -zoom_input
                    self.input_state['forward'] = 0.0

                # Right stick X could control roll when shift is simulated
                # For now, we can use triggers or buttons for shift
                # Check if right stick is being used significantly
                if abs(right_x) > 0.1:
                    self.shift_pressed = True
                else:
                    self.shift_pressed = False

            # Optional: Use triggers for zoom (axis 4/5 on some controllers)
            # Optional: Use D-pad for discrete movements (hat 0)

        except Exception as e:
            print(f"Warning: Error reading gamepad: {e}")

        return self.input_state

    def get_input_state(self) -> Dict[str, float]:
        """Get current camera input state."""
        return self.input_state

    def is_shift_pressed(self) -> bool:
        """Check if shift modifier is active (right stick X movement)."""
        return self.shift_pressed

    def cleanup(self):
        """Clean up gamepad resources."""
        if self.joystick:
            try:
                self.joystick.quit()
            except:
                pass
            self.joystick = None

    def is_connected(self) -> bool:
        """Check if gamepad is connected."""
        return self.joystick is not None


def list_gamepads(pygame_module):
    """
    List all connected gamepads.

    Args:
        pygame_module: The pygame module

    Returns:
        List of (index, name) tuples
    """
    pygame_module.joystick.init()

    gamepads = []
    for i in range(pygame_module.joystick.get_count()):
        try:
            joystick = pygame_module.joystick.Joystick(i)
            joystick.init()
            gamepads.append((i, joystick.get_name()))
            joystick.quit()
        except Exception as e:
            print(f"Warning: Could not query joystick {i}: {e}")

    return gamepads
