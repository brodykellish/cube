"""
Volumetric Cube Renderer

Renders a 3D scene from 6 perspectives (one for each face of a physical LED cube).
Each face shows a 2D projection of the 3D scene from its perspective, creating
a volumetric effect where the cube appears to contain a 3D object.

Architecture:
- Uses 6 StaticCamera instances (one per cube face)
- Single shader renders from all 6 perspectives
- Returns 6 pixel arrays (one per face)
- Supports both preview mode (pygame) and LED output mode
"""

import numpy as np
from typing import Dict, Tuple, Optional
from pathlib import Path

# Import shader module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from piomatter.shader import (
    ShaderRenderer, StaticCamera
)


class CubeFace:
    """Represents one face of the cube with its camera configuration."""

    def __init__(self, name: str, position: Tuple[float, float, float],
                 look_at: Tuple[float, float, float]):
        """
        Initialize a cube face.

        Args:
            name: Face name (front, back, left, right, top, bottom)
            position: Camera position for this face
            look_at: Point camera looks at (usually origin)
        """
        self.name = name
        self.position = position
        self.look_at = look_at
        self.camera = StaticCamera(position, look_at)


class VolumetricCubeRenderer:
    """
    Renders a 3D scene from 6 perspectives for volumetric LED cube display.

    Each face of the cube gets its own 2D projection of the 3D scene,
    creating the illusion of a volumetric 3D object inside the cube.
    """

    # Define the 6 cube faces with their camera positions
    # Assumes cube centered at origin, faces at distance 'face_distance'
    FACE_CONFIGS = {
        'front': {
            'position': (0.0, 0.0, 1.0),  # +Z axis
            'look_at': (0.0, 0.0, 0.0),
        },
        'back': {
            'position': (0.0, 0.0, -1.0),  # -Z axis
            'look_at': (0.0, 0.0, 0.0),
        },
        'left': {
            'position': (-1.0, 0.0, 0.0),  # -X axis
            'look_at': (0.0, 0.0, 0.0),
        },
        'right': {
            'position': (1.0, 0.0, 0.0),  # +X axis
            'look_at': (0.0, 0.0, 0.0),
        },
        'top': {
            'position': (0.0, 1.0, 0.0),  # +Y axis (up)
            'look_at': (0.0, 0.0, 0.0),
        },
        'bottom': {
            'position': (0.0, -1.0, 0.0),  # -Y axis (down)
            'look_at': (0.0, 0.0, 0.0),
        },
    }

    def __init__(self, face_size: int = 64, face_distance: float = 5.0, num_panels: int = 6):
        """
        Initialize volumetric cube renderer.

        Args:
            face_size: Width/height of each face in pixels
            face_distance: Distance of camera from origin for each face
            num_panels: Number of cube panels/faces to render (1-6)
        """
        self.face_size = face_size
        self.face_distance = face_distance
        self.num_panels = min(max(1, num_panels), 6)  # Clamp to 1-6

        # Determine which faces to use (in order)
        face_order = ['front', 'back', 'left', 'right', 'top', 'bottom']
        self.active_faces = face_order[:self.num_panels]

        # Create cube faces with scaled positions (only for active faces)
        self.faces: Dict[str, CubeFace] = {}
        for name in self.active_faces:
            config = self.FACE_CONFIGS[name]
            pos = tuple(c * face_distance for c in config['position'])
            self.faces[name] = CubeFace(name, pos, config['look_at'])

        # Create a single shader renderer (will be reused with different cameras)
        self.renderer = ShaderRenderer(face_size, face_size, windowed=False)

        print(f"Volumetric cube renderer initialized: {face_size}×{face_size} per face")
        print(f"Number of panels: {self.num_panels}")
        print(f"Active faces: {', '.join(self.active_faces)}")
        print(f"Camera distance from origin: {face_distance}")

    def load_shader(self, shader_path: str):
        """
        Load a shader for volumetric rendering.

        Args:
            shader_path: Path to .glsl shader file
        """
        self.renderer.load_shader(shader_path)
        print(f"Loaded volumetric shader: {shader_path}")

    def render_face(self, face_name: str) -> np.ndarray:
        """
        Render a single face of the cube.

        Args:
            face_name: Name of face to render (front, back, left, right, top, bottom)

        Returns:
            Pixel array of shape (face_size, face_size, 3)
        """
        if face_name not in self.faces:
            raise ValueError(f"Unknown face: {face_name}")

        face = self.faces[face_name]

        # Set camera for this face
        self.renderer.set_camera_mode(face.camera)

        # Render
        self.renderer.render()

        # Read pixels
        return self.renderer.read_pixels()

    def render_all_faces(self) -> Dict[str, np.ndarray]:
        """
        Render all active faces of the cube.

        Returns:
            Dictionary mapping face name -> pixel array (only for active faces)
        """
        return {
            name: self.render_face(name)
            for name in self.faces.keys()
        }

    def get_face_order(self) -> list:
        """Get active face ordering for consistent layout."""
        return self.active_faces

    def cleanup(self):
        """Clean up resources."""
        self.renderer.cleanup()


class CubePreviewRenderer:
    """
    Preview renderer for volumetric cube in pygame window.

    Arranges active faces in a dynamic layout based on num_panels.
    """

    def __init__(self, cube_renderer: VolumetricCubeRenderer, scale: int = 4):
        """
        Initialize preview renderer.

        Args:
            cube_renderer: VolumetricCubeRenderer instance
            scale: Scale factor for display
        """
        self.cube = cube_renderer
        self.scale = scale
        self.face_size = cube_renderer.face_size
        self.num_panels = cube_renderer.num_panels

        # Dynamic layout based on num_panels
        if self.num_panels == 6:
            # Cross pattern for 6 faces
            #       [top]
            # [left][front][right][back]
            #       [bottom]
            self.layout = {
                'top':    (1, 0),  # (x, y) in grid
                'left':   (0, 1),
                'front':  (1, 1),
                'right':  (2, 1),
                'back':   (3, 1),
                'bottom': (1, 2),
            }
            grid_width, grid_height = 4, 3
        else:
            # Simple grid layout for 1-5 faces
            self.layout = {}
            active_faces = cube_renderer.active_faces

            if self.num_panels == 1:
                grid_width, grid_height = 1, 1
            elif self.num_panels == 2:
                grid_width, grid_height = 2, 1
            elif self.num_panels == 3:
                grid_width, grid_height = 3, 1
            elif self.num_panels == 4:
                grid_width, grid_height = 2, 2
            else:  # 5 panels
                grid_width, grid_height = 3, 2

            for i, face_name in enumerate(active_faces):
                if self.num_panels <= 3:
                    self.layout[face_name] = (i, 0)
                elif self.num_panels == 4:
                    self.layout[face_name] = (i % 2, i // 2)
                else:  # 5 panels
                    self.layout[face_name] = (i % 3, i // 3)

        # Window size based on grid dimensions
        self.window_width = grid_width * self.face_size * scale
        self.window_height = grid_height * self.face_size * scale

        # Initialize pygame
        import pygame
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption(f"Volumetric Cube Preview - {self.num_panels} Face{'s' if self.num_panels > 1 else ''}")
        self.clock = pygame.time.Clock()

        print(f"Preview window: {self.window_width}×{self.window_height} ({self.num_panels} faces)")

    def render_frame(self):
        """Render one frame of the preview."""
        import pygame

        # Render all faces
        faces = self.cube.render_all_faces()

        # Clear screen
        self.screen.fill((0, 0, 0))

        # Draw each face in its position
        for name, pixels in faces.items():
            grid_x, grid_y = self.layout[name]

            # Convert numpy array to pygame surface
            # Flip vertically because pygame uses top-left origin
            surface = pygame.surfarray.make_surface(np.swapaxes(pixels, 0, 1))

            # Scale up
            if self.scale > 1:
                surface = pygame.transform.scale(
                    surface,
                    (self.face_size * self.scale, self.face_size * self.scale)
                )

            # Blit to screen
            x = grid_x * self.face_size * self.scale
            y = grid_y * self.face_size * self.scale
            self.screen.blit(surface, (x, y))

            # Draw face label
            font = pygame.font.Font(None, 24)
            text = font.render(name.upper(), True, (255, 255, 255))
            text_rect = text.get_rect(center=(
                x + (self.face_size * self.scale) // 2,
                y + 10
            ))
            self.screen.blit(text, text_rect)

        pygame.display.flip()

    def run(self, fps: int = 30):
        """
        Run interactive preview loop.

        Args:
            fps: Target frames per second
        """
        import pygame

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        running = False

            self.render_frame()
            self.clock.tick(fps)

        pygame.quit()
        self.cube.cleanup()


def main():
    """Example usage."""
    # Create volumetric cube renderer
    cube = VolumetricCubeRenderer(face_size=64, face_distance=5.0)

    # Load a shader (will create a simple one if not exists)
    shader_path = Path(__file__).parent / "shaders" / "torus.glsl"
    if not shader_path.exists():
        print(f"Shader not found: {shader_path}")
        print("Please create a volumetric shader first!")
        return

    cube.load_shader(str(shader_path))

    # Create preview renderer
    preview = CubePreviewRenderer(cube, scale=4)

    # Run preview
    print("\nRunning volumetric cube preview...")
    print("Press ESC or Q to quit")
    preview.run(fps=30)


if __name__ == "__main__":
    main()
