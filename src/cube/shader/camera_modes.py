"""
Camera modes for shader navigation.

Provides different camera control schemes (spherical, FPS, etc.) with a
unified interface.
"""

import time
import math
from abc import ABC, abstractmethod
from typing import Tuple, Dict


class CameraMode(ABC):
    """
    Abstract base class for camera control modes.

    Each mode handles input and computes camera vectors differently.
    """

    def __init__(self):
        """Initialize camera mode."""
        self.last_update_time = time.time()

    @abstractmethod
    def update(self, input_state: Dict[str, float], dt: float, shift_pressed: bool = False):
        """
        Update camera state based on input.

        Args:
            input_state: Dict with keys 'up', 'down', 'left', 'right', 'forward', 'backward'
                        Values are 0.0 (not pressed) or 1.0 (pressed)
            dt: Delta time since last update (seconds)
            shift_pressed: Whether shift modifier is held
        """
        pass

    @abstractmethod
    def get_vectors(self) -> Tuple[Tuple[float, float, float], ...]:
        """
        Get camera position and orientation vectors.

        Returns:
            (pos, right, up, forward) where each is a 3-tuple of floats
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset camera to default position/orientation."""
        pass


class SphericalCamera(CameraMode):
    """
    Spherical coordinate camera mode.

    Camera orbits around the origin using spherical coordinates (yaw, pitch, distance).
    - Left/Right: Rotate yaw (horizontal)
    - Up/Down: Rotate pitch (vertical) OR zoom (with shift)
    - Forward/Backward: Zoom in/out
    - Shift modifier: Changes up/down from pitch to zoom

    Features:
    - Smooth acceleration and damping
    - No gimbal lock (uses proper spherical math)
    - Full 360° rotation on all axes
    - Frame-rate independent
    """

    def __init__(
        self,
        distance: float = 12.0,
        yaw: float = 0.785,  # ~45 degrees
        pitch: float = 0.6,  # ~34 degrees
        rotate_speed: float = 1.5,
        zoom_speed: float = 5.0,
        damping: float = 0.9,
        min_distance: float = 1.0,
        max_distance: float = 50.0
    ):
        """
        Initialize spherical camera.

        Args:
            distance: Initial distance from origin
            yaw: Initial horizontal angle (radians)
            pitch: Initial vertical angle (radians)
            rotate_speed: Rotation speed (radians per second)
            zoom_speed: Zoom speed (units per second)
            damping: Velocity damping (0=instant stop, 1=no damping)
            min_distance: Minimum distance from origin
            max_distance: Maximum distance from origin
        """
        super().__init__()

        # Spherical coordinates
        self.distance = distance
        self.yaw = yaw
        self.pitch = pitch

        # Velocities
        self.distance_vel = 0.0
        self.yaw_vel = 0.0
        self.pitch_vel = 0.0

        # Parameters
        self.rotate_speed = rotate_speed
        self.zoom_speed = zoom_speed
        self.damping = damping
        self.min_distance = min_distance
        self.max_distance = max_distance

        # Store initial values for reset
        self.initial_distance = distance
        self.initial_yaw = yaw
        self.initial_pitch = pitch

    def update(self, input_state: Dict[str, float], dt: float, shift_pressed: bool = False):
        """Update camera based on input with smooth acceleration and damping."""
        # Get input values
        input_lr = input_state['right'] - input_state['left']
        input_ud = input_state['up'] - input_state['down']
        input_fb = input_state['forward'] - input_state['backward']

        # Acceleration multiplier (makes controls more responsive)
        accel = 5.0

        # Left/Right: Rotate yaw (horizontal rotation)
        self.yaw_vel += input_lr * self.rotate_speed * accel * dt

        # Up/Down behavior depends on shift key
        if shift_pressed:
            # Shift + Up/Down: Zoom in/out (change distance)
            self.distance_vel -= input_ud * self.zoom_speed * accel * dt
        else:
            # Up/Down: Rotate pitch (vertical rotation around origin)
            self.pitch_vel += input_ud * self.rotate_speed * accel * dt

        # Forward/Backward: Also zoom in/out
        self.distance_vel -= input_fb * self.zoom_speed * accel * dt

        # Apply frame-rate independent damping
        damping = self.damping ** (dt * 60.0)
        self.yaw_vel *= damping
        self.pitch_vel *= damping
        self.distance_vel *= damping

        # Update spherical coordinates
        self.yaw += self.yaw_vel * dt
        self.pitch += self.pitch_vel * dt
        self.distance += self.distance_vel * dt

        # No pitch clamping - allow full 360° rotation!

        # Clamp distance to reasonable range
        self.distance = max(self.min_distance, min(self.max_distance, self.distance))

    def get_vectors(self) -> Tuple[Tuple[float, float, float], ...]:
        """Compute camera position and orientation vectors from spherical coordinates."""
        # Convert spherical to cartesian for camera position
        x = self.distance * math.cos(self.pitch) * math.sin(self.yaw)
        y = self.distance * math.sin(self.pitch)
        z = self.distance * math.cos(self.pitch) * math.cos(self.yaw)
        pos = (x, y, z)

        # Forward vector: always points toward origin (normalized)
        forward = (-x, -y, -z)
        f_len = math.sqrt(forward[0]**2 + forward[1]**2 + forward[2]**2)
        if f_len > 0:
            forward = (forward[0]/f_len, forward[1]/f_len, forward[2]/f_len)
        else:
            forward = (0.0, 0.0, -1.0)  # Fallback

        # Right vector: tangent to circle of latitude (derivative w.r.t. yaw)
        # Naturally perpendicular to forward and continuous everywhere
        right = (math.cos(self.yaw), 0.0, -math.sin(self.yaw))

        # Up vector: tangent to meridian (derivative w.r.t. pitch)
        # Naturally perpendicular to forward and continuous everywhere
        up = (
            -math.sin(self.pitch) * math.sin(self.yaw),
            math.cos(self.pitch),
            -math.sin(self.pitch) * math.cos(self.yaw)
        )

        return pos, right, up, forward

    def reset(self):
        """Reset camera to initial position."""
        self.distance = self.initial_distance
        self.yaw = self.initial_yaw
        self.pitch = self.initial_pitch
        self.distance_vel = 0.0
        self.yaw_vel = 0.0
        self.pitch_vel = 0.0


class StaticCamera(CameraMode):
    """
    Static camera mode with no movement.

    Camera stays at a fixed position with fixed orientation.
    Input is ignored (but still passed to shader via iInput uniform).

    Best for:
    - Shaders that don't use camera vectors
    - Shaders with custom navigation
    - Viewing non-3D effects
    """

    def __init__(
        self,
        position: Tuple[float, float, float] = (0.0, 0.0, -5.0),
        look_at: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    ):
        """
        Initialize static camera.

        Args:
            position: Camera position
            look_at: Point camera looks at (to compute forward direction)
        """
        super().__init__()
        self.position = position
        self.look_at = look_at

        # Store for reset
        self.initial_position = position
        self.initial_look_at = look_at

        # Pre-compute vectors
        self._compute_vectors()

    def _compute_vectors(self):
        """Compute camera orientation vectors from position and look_at."""
        # Forward: from camera to look_at
        forward = (
            self.look_at[0] - self.position[0],
            self.look_at[1] - self.position[1],
            self.look_at[2] - self.position[2]
        )
        f_len = math.sqrt(forward[0]**2 + forward[1]**2 + forward[2]**2)
        if f_len > 0:
            forward = (forward[0]/f_len, forward[1]/f_len, forward[2]/f_len)
        else:
            forward = (0.0, 0.0, -1.0)

        # Right: cross(world_up, forward)
        world_up = (0.0, 1.0, 0.0)
        right = (
            world_up[1] * forward[2] - world_up[2] * forward[1],
            world_up[2] * forward[0] - world_up[0] * forward[2],
            world_up[0] * forward[1] - world_up[1] * forward[0]
        )
        r_len = math.sqrt(right[0]**2 + right[1]**2 + right[2]**2)
        if r_len > 0:
            right = (right[0]/r_len, right[1]/r_len, right[2]/r_len)
        else:
            right = (1.0, 0.0, 0.0)

        # Up: cross(forward, right)
        up = (
            forward[1] * right[2] - forward[2] * right[1],
            forward[2] * right[0] - forward[0] * right[2],
            forward[0] * right[1] - forward[1] * right[0]
        )

        self._pos = self.position
        self._right = right
        self._up = up
        self._forward = forward

    def update(self, input_state: Dict[str, float], dt: float, shift_pressed: bool = False):
        """Static camera doesn't move - ignore input."""
        pass

    def get_vectors(self) -> Tuple[Tuple[float, float, float], ...]:
        """Return pre-computed static vectors."""
        return self._pos, self._right, self._up, self._forward

    def reset(self):
        """Reset to initial position."""
        self.position = self.initial_position
        self.look_at = self.initial_look_at
        self._compute_vectors()


# Future camera modes can be added here:
#
# class FPSCamera(CameraMode):
#     """
#     First-person shooter style camera.
#
#     Camera moves freely in 3D space with ground plane constraint.
#     - WASD: Move horizontally
#     - Up/Down: Look up/down
#     - Left/Right: Turn left/right
#     - Shift+Space: Move up/down
#     """
#     pass
#
# class FlyingCamera(CameraMode):
#     """
#     Free-flying camera like a bird.
#
#     Camera flies above a horizon plane with banking on turns.
#     - WASD: Move forward/backward/strafe
#     - Up/Down: Pitch up/down
#     - Left/Right: Yaw left/right (with banking)
#     """
#     pass
