"""
Video source node implementation for cube.

VideoSourceNode produces a texture from video frames without using a shader.
"""
from typing import Optional
import numpy as np
import cv2
from .node import Node
from .frame_loader import FrameLoader


class VideoSourceNode(Node):
    """
    Source node that produces a texture from video frames.
    
    Does not use a shader program - directly uploads frames to the output texture.
    Respects the video's FPS by only advancing frames when enough time has passed.
    """
    
    def __init__(self, name: str, frame_loader: FrameLoader, width: int, height: int):
        """
        Initialize video source node.
        
        Args:
            name: Node identifier
            frame_loader: FrameLoader instance that provides frames
            width: Output width
            height: Output height
        """
        super().__init__(name, shader=None, width=width, height=height)
        self.frame_loader = frame_loader
        # Ensure texture is created immediately so effects can use it
        self.output_texture.create()
        # Initialize with a checkerboard pattern so we can tell if this frame is being rendered
        checkerboard_frame = self._create_checkerboard(width, height)
        self.output_texture.upload_pixels(checkerboard_frame)
    
    def _create_checkerboard(self, width: int, height: int, checker_size: int = 32) -> np.ndarray:
        """
        Create a checkerboard pattern frame.
        
        Args:
            width: Frame width
            height: Frame height
            checker_size: Size of each checker square in pixels
            
        Returns:
            RGBA numpy array with checkerboard pattern
        """
        # Create coordinate grids
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        # Determine checker pattern: (x // checker_size + y // checker_size) % 2 == 0 is white
        checker_pattern = ((x_coords // checker_size + y_coords // checker_size) % 2 == 0)
        # Create RGBA frame: white where pattern is True, black otherwise
        frame = np.zeros((height, width, 4), dtype=np.uint8)
        frame[checker_pattern] = [255, 255, 255, 255]  # White squares
        frame[~checker_pattern] = [0, 0, 0, 255]  # Black squares
        return frame
    
    def render(self, t: float, resolution: tuple[float, float], uniforms: dict=None, input_texture_id: Optional[int]=None, shader_textures: Optional[dict]=None):
        """
        Render video source node by loading current frame at the correct FPS.
        
        Args:
            t: Current time in seconds (passed to frame loader for FPS timing)
            resolution: Resolution as (width, height) (unused, but required by interface)
            uniforms: Unused (no shader)
            input_texture_id: Unused (no shader)
            shader_textures: Unused (no shader)
        """
        if not self.enabled:
            return
        
        # Ensure texture is created
        if not self.output_texture._created:
            self.output_texture.create()
        
        # Get current frame from loader (handles FPS timing internally)
        frame = self.frame_loader.get_current_frame(t)
        
        if frame is not None:
            # Resize frame to match texture size if needed
            frame_height, frame_width = frame.shape[:2]
            if frame_width != self.width or frame_height != self.height:
                frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
            
            # Convert RGB to RGBA if needed (texture is RGBA format)
            # Optimize: only convert if not already RGBA
            if frame.shape[2] == 3:
                # Add alpha channel (fully opaque) - more efficient than full conversion
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA)
            
            # Upload to texture (this is the expensive OpenGL operation)
            self.output_texture.upload_pixels(frame)
    
    def cleanup(self):
        """Clean up node resources."""
        if self.frame_loader is not None:
            self.frame_loader.cleanup()
        super().cleanup()

