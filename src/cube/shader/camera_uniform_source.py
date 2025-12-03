"""
Camera Uniform Source - provides camera vectors as shader uniforms.

Makes the camera a proper uniform source, following the same pattern
as MIDI, audio, keyboard, etc. This eliminates special-case camera handling.
"""

from typing import Dict, Any
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

    def __init__(self, camera: CameraMode = None):
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

        # Temporary override for multi-pass rendering (e.g., cube faces)
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
        # Update camera from input state
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Clamp dt to prevent huge jumps
        if dt > 0.1:
            dt = 0.1

        self.camera.update(self.input_state, dt, self.shift_pressed)

    def get_uniforms(self) -> Dict[str, Any]:
        """
        Get camera position and orientation vectors as uniforms.

        Returns:
            Dictionary with camera uniforms
        """
        # Use override vectors if set (for multi-pass rendering)
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
        Temporarily override camera vectors for multi-pass rendering.

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
