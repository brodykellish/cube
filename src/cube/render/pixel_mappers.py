"""
Pixel mapping strategies for shader rendering.

Defines how shader renders map to final display framebuffer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
import numpy as np

from cube.shader.camera_modes import CameraMode, StaticCamera, SphericalCamera


@dataclass
class RenderSpec:
    """Specification for a single render pass."""
    width: int          # Render resolution width
    height: int         # Render resolution height
    camera: CameraMode  # Camera configuration


class PixelMapper(ABC):
    """
    Abstract pixel mapping strategy.

    Defines how shader renders map to the final framebuffer.
    """

    @abstractmethod
    def get_render_specs(self) -> List[RenderSpec]:
        """Get list of render passes needed."""
        pass

    @abstractmethod
    def layout_renders(self, renders: List[np.ndarray]) -> np.ndarray:
        """Combine renders into final framebuffer."""
        pass

    @abstractmethod
    def get_output_dimensions(self) -> tuple:
        """Get final output dimensions (width, height)."""
        pass


class SurfacePixelMapper(PixelMapper):
    """
    Single render covering full display surface.

    Traditional 2D shader mode - one render, user-controlled camera.
    """

    def __init__(self, width: int, height: int, camera: CameraMode):
        self.width = width
        self.height = height
        self.camera = camera

    def get_render_specs(self) -> List[RenderSpec]:
        return [RenderSpec(self.width, self.height, self.camera)]

    def layout_renders(self, renders: List[np.ndarray]) -> np.ndarray:
        return renders[0]

    def get_output_dimensions(self) -> tuple:
        return (self.width, self.height)


class CubePixelMapper(PixelMapper):
    """
    Cube renderer - render shader on cube faces with rotation controls.

    Controls:
    - Left/Right: Rotate cube around Y-axis
    - Up/Down: Rotate cube around X-axis
    - Shift+Up/Down: Zoom in/out
    """

    # Cube face camera configurations
    FACE_CONFIGS = {
        'front':  {'position': (0.0, 0.0, 1.0),  'look_at': (0.0, 0.0, 0.0)},
        'right':  {'position': (1.0, 0.0, 0.0),  'look_at': (0.0, 0.0, 0.0)},
        'back':   {'position': (0.0, 0.0, -1.0), 'look_at': (0.0, 0.0, 0.0)},
        'left':   {'position': (-1.0, 0.0, 0.0), 'look_at': (0.0, 0.0, 0.0)},
        'top':    {'position': (0.0, 1.0, 0.0),  'look_at': (0.0, 0.0, 0.0)},
        'bottom': {'position': (0.0, -1.0, 0.0), 'look_at': (0.0, 0.0, 0.0)},
    }

    def __init__(self, face_width: int = None, face_height: int = None, num_panels: int = 6,
                 face_distance: float = 5.0, face_size: int = None):
        """
        Initialize cube pixel mapper.

        Args:
            face_width: Width of each face panel
            face_height: Height of each face panel
            num_panels: Number of cube faces to render (1-6)
            face_distance: Camera distance from cube center
            face_size: Legacy parameter for square faces (deprecated, use face_width/face_height)
        """
        # Handle legacy face_size parameter for backward compatibility
        if face_size is not None and face_width is None and face_height is None:
            face_width = face_size
            face_height = face_size
        elif face_width is None or face_height is None:
            raise ValueError("Must specify either face_size or both face_width and face_height")

        self.face_width = face_width
        self.face_height = face_height
        self.num_panels = min(max(1, num_panels), 6)
        self.base_distance = face_distance

        # Use SphericalCamera for all rotation logic (yaw, pitch, roll, zoom)
        self.camera = SphericalCamera(distance=face_distance)

        # Active faces (matches physical cube wiring order)
        face_order = ['front', 'right', 'back', 'left', 'top', 'bottom']
        self.active_faces = face_order[:self.num_panels]

    def get_render_specs(self) -> List[RenderSpec]:
        # One render per active face (can be rectangular)
        # Note: camera field in RenderSpec is now ignored, kept for compatibility
        return [
            RenderSpec(self.face_width, self.face_height, None)
            for _ in self.active_faces
        ]

    def reposition_camera_for_face(self, face_index: int, camera_source):
        """
        Temporarily reposition the camera to view from a specific face.

        The main camera (SphericalCamera) controls rotation/zoom of the entire cube.
        This method repositions the viewpoint to see from one face of the cube.

        Args:
            face_index: Index of the face to render (0-5)
            camera_source: CameraUniformSource to temporarily override
        """
        face_name = self.active_faces[face_index]
        config = self.FACE_CONFIGS[face_name]

        # Compute the camera position for this face based on current rotation/zoom
        pos = self._compute_camera_position(face_name, config)
        look_at = config['look_at']

        # Create a temporary StaticCamera to compute the proper view vectors
        temp_camera = StaticCamera(pos, look_at)
        vectors = temp_camera.get_vectors()

        # Temporarily override the camera vectors for this render pass
        camera_source.set_override_vectors(vectors)

    def _compute_camera_position(self, face_name: str, config: dict) -> tuple:
        """
        Compute camera position based on face rotation and zoom.
        Applies rotations in order: Yaw (Y) → Pitch (X) → Roll (Z)
        """
        base_pos = config['position']

        # Get distance with zoom from SphericalCamera
        distance = self.camera.distance

        # Apply rotation transforms
        import math

        # Extract rotation angles from SphericalCamera
        yaw = self.camera.yaw
        pitch = self.camera.pitch
        roll = self.camera.roll

        # Pre-compute trig values
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        cos_roll = math.cos(roll)
        sin_roll = math.sin(roll)

        # Start with base position
        x, y, z = base_pos

        # Apply rotations in order: Yaw → Pitch → Roll

        # 1. Yaw rotation (around Y-axis)
        x_rot = x * cos_yaw + z * sin_yaw
        z_rot = -x * sin_yaw + z * cos_yaw
        x, z = x_rot, z_rot

        # 2. Pitch rotation (around X-axis)
        y_rot = y * cos_pitch - z * sin_pitch
        z_rot = y * sin_pitch + z * cos_pitch
        y, z = y_rot, z_rot

        # 3. Roll rotation (around Z-axis)
        x_rot = x * cos_roll - y * sin_roll
        y_rot = x * sin_roll + y * cos_roll
        x, y = x_rot, y_rot

        # Apply distance
        x *= distance
        y *= distance
        z *= distance

        return (x, y, z)

    def layout_renders(self, renders: List[np.ndarray]) -> np.ndarray:
        # Horizontal chain layout
        chain = np.hstack(renders)
        return chain

    def get_output_dimensions(self) -> tuple:
        return (self.face_width * self.num_panels, self.face_height)
