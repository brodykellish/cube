"""
Camera Uniform Source - provides camera vectors as shader uniforms.

Makes the camera a proper uniform source, following the same pattern
as MIDI, audio, keyboard, etc. This eliminates special-case camera handling.
"""

from typing import Dict, Any, Optional
import time
from .uniform_sources import UniformSource
from .camera_modes import CameraMode, SphericalCamera


class CameraUniformSource(UniformSource):
    """
    Provides camera position and orientation as shader uniforms.

    Uniforms provided:
    - iCameraPos (vec3): Camera position in world space
    - iCameraRight (vec3): Camera right vector
    - iCameraUp (vec3): Camera up vector
    - iCameraForward (vec3): Camera forward vector

    The camera updates based on input state set via set_key_state().
    """

    def __init__(self, camera: CameraMode = None, input_manager: Optional[object] = None):
        """
        Initialize camera uniform source.

        Args:
            camera: Camera mode instance (default: SphericalCamera)
        """
        if camera is None:
            camera = SphericalCamera(
                distance=12.0,
                yaw=0.785,
                pitch=0.6,
                rotate_speed=1.5,
                zoom_speed=5.0,
                damping=0.9
            )

        self.camera = camera
        self.last_update_time = time.time()
        # Optional InputManager for axis-driven camera control.
        self._input_manager = input_manager

        # Input state (updated by controller via set_key_state)
        self.input_state = {
            'left': 0.0,
            'right': 0.0,
            'up': 0.0,
            'down': 0.0,
            'forward': 0.0,
            'backward': 0.0,
        }

        self.shift_pressed = False

        # Temporary override for cube face rendering
        self._override_vectors = None

    def set_key_state(self, key: str, pressed: bool):
        """
        Update camera input state.

        Called by controller when camera control keys are pressed/released.

        Args:
            key: Key name ('left', 'right', 'up', 'down', 'forward', 'backward')
            pressed: True if pressed, False if released
        """
        if key in self.input_state:
            self.input_state[key] = 1.0 if pressed else 0.0
        elif key == 'shift':
            self.shift_pressed = pressed

    def update(self, dt: float):
        """
        Update camera based on input state.

        Args:
            dt: Delta time since last update
        """
        # Derive input state from InputManager axes when available.
        local_shift = self.shift_pressed

        if self._input_manager is not None:
            try:
                from cube.input.actions import Axis  # Local import to avoid cycles

                pitch = self._input_manager.get_axis(Axis.CAMERA_PITCH, 0.0)
                yaw = self._input_manager.get_axis(Axis.CAMERA_YAW, 0.0)
                zoom = self._input_manager.get_axis(Axis.CAMERA_ZOOM, 0.0)
                roll = self._input_manager.get_axis(Axis.CAMERA_ROLL, 0.0)

                # Map axes into the discrete input_state expected by CameraMode.
                threshold = 0.1
                self.input_state["up"] = 1.0 if pitch > threshold else 0.0
                self.input_state["down"] = 1.0 if pitch < -threshold else 0.0
                self.input_state["right"] = 1.0 if yaw > threshold else 0.0
                self.input_state["left"] = 1.0 if yaw < -threshold else 0.0
                self.input_state["forward"] = 1.0 if zoom > threshold else 0.0
                self.input_state["backward"] = 1.0 if zoom < -threshold else 0.0

                # Roll: treat as shift+left/right so CameraMode routes to roll.
                if abs(roll) > threshold:
                    self.input_state["right"] = 1.0 if roll > threshold else 0.0
                    self.input_state["left"] = 1.0 if roll < -threshold else 0.0
                    local_shift = True
            except Exception:
                # Fall back to existing input_state values if anything goes wrong.
                pass

        # Update camera from (possibly updated) input_state
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Clamp dt to prevent huge jumps
        if dt > 0.1:
            dt = 0.1

        self.camera.update(self.input_state, dt, local_shift)

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get camera position and orientation vectors as uniforms.

        Returns:
            Dictionary with camera uniforms
        """
        # Use override vectors if set (for cube face rendering)
        if self._override_vectors is not None:
            pos, right, up, forward = self._override_vectors
        else:
            pos, right, up, forward = self.camera.get_vectors()

        return {
            'iCameraPos': pos,
            'iCameraRight': right,
            'iCameraUp': up,
            'iCameraForward': forward,
        }

    def set_override_vectors(self, vectors):
        """
        Temporarily override camera vectors for cube face rendering.

        Args:
            vectors: (pos, right, up, forward) tuple or None to clear override
        """
        self._override_vectors = vectors

    def get_camera(self) -> CameraMode:
        """Get the underlying camera instance."""
        return self.camera

    def reset_camera(self):
        """Reset camera to default position."""
        self.camera.reset()

    def cleanup(self):
        """No cleanup needed for camera."""
        pass

    def reset(self):
        """Reset camera and input state."""
        self.camera.reset()
        for key in self.input_state:
            self.input_state[key] = 0.0
        self.shift_pressed = False
