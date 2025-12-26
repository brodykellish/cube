"""
Frame loader abstraction for video source nodes.

Separates the concern of "loading frames from a source" from "exposing frames as textures".
"""
from abc import ABC, abstractmethod
from typing import Optional, Iterator
import numpy as np
from pathlib import Path

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class FrameLoader(ABC):
    """
    Abstract base class for loading frames from various sources.
    
    Provides a generator interface for yielding frames one at a time.
    """
    
    @abstractmethod
    def frames(self) -> Iterator[np.ndarray]:
        """
        Generator that yields frames from the source.
        
        Yields:
            RGB frame as numpy array (H, W, 3) with dtype uint8
        """
        pass
    
    @abstractmethod
    def get_properties(self) -> dict:
        """
        Get frame source properties.
        
        Returns:
            Dictionary with 'width', 'height', 'fps' (if applicable)
        """
        pass
    
    def get_current_frame(self, t: float) -> Optional[np.ndarray]:
        """
        Get the current frame based on time, respecting FPS timing.
        
        This method handles FPS timing internally and returns the same frame
        until enough time has passed to advance to the next frame.
        
        Args:
            t: Current time in seconds
            
        Returns:
            Current frame as numpy array (H, W, 3) with dtype uint8, or None
        """
        # Default implementation: just return next frame from generator
        # Subclasses should override to implement FPS timing
        return next(self.frames(), None)
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources."""
        pass


class VideoFileFrameLoader(FrameLoader):
    """Loads frames from a video file using OpenCV."""
    
    def __init__(self, file_path: Path, loop: bool = True):
        """
        Initialize video file frame loader.
        
        Args:
            file_path: Path to video file
            loop: Whether to loop the video when it ends
        """
        if not CV2_AVAILABLE:
            raise RuntimeError('opencv-python is required for video support')
        
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f'Video file not found: {file_path}')
        
        self.loop = loop
        self.cap = None
        self.width = 0
        self.height = 0
        self.fps = 30.0
        self.frame_duration = None
        self.current_frame = None
        self.last_frame_time = None
        self.frame_generator = None
        self._open()
        
        # Calculate frame duration from FPS
        self.frame_duration = 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0
    
    def _open(self):
        """Open video file with OpenCV."""
        try:
            self.cap = cv2.VideoCapture(str(self.file_path))
            if not self.cap.isOpened():
                raise RuntimeError(f'Failed to open video: {self.file_path}')
            
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30.0
            
            print(f'Video loaded: {self.file_path.name}')
            print(f'  Resolution: {self.width}×{self.height}')
            print(f'  FPS: {self.fps:.1f}')
        except Exception as e:
            print(f'Error opening video: {e}')
            raise
    
    def frames(self) -> Iterator[np.ndarray]:
        """
        Generator that yields frames from the video file.
        
        Yields:
            RGB frame as numpy array (H, W, 3) with dtype uint8
        """
        if self.cap is None:
            return
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                if self.loop:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                else:
                    break
            
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.flip(frame, 0)
                frame = np.ascontiguousarray(frame, dtype=np.uint8)
                yield frame
            else:
                break
    
    def get_current_frame(self, t: float) -> Optional[np.ndarray]:
        """
        Get the current frame based on time, respecting video FPS.
        
        Returns the same frame until enough time has passed (based on video FPS)
        to advance to the next frame.
        
        Args:
            t: Current time in seconds
            
        Returns:
            Current frame as numpy array (H, W, 3) with dtype uint8, or None
        """
        if self.cap is None:
            return None
        
        # Initialize frame generator and timing on first call
        if self.frame_generator is None:
            self.frame_generator = self.frames()
            self.last_frame_time = t
        
        # Check if enough time has passed to advance to next frame
        time_since_last_frame = t - self.last_frame_time
        should_advance = time_since_last_frame >= self.frame_duration
        
        if should_advance:
            # Advance to next frame
            try:
                frame = next(self.frame_generator)
                if frame is not None:
                    self.current_frame = frame
                    self.last_frame_time = t
                    return frame
            except StopIteration:
                # Video ended, restart if looping
                if self.loop:
                    self.frame_generator = self.frames()
                    try:
                        frame = next(self.frame_generator)
                        if frame is not None:
                            self.current_frame = frame
                            self.last_frame_time = t
                            return frame
                    except StopIteration:
                        pass
                return None
        
        # Not enough time has passed, return current frame
        return self.current_frame
    
    def get_properties(self) -> dict:
        """Get video properties."""
        return {
            'width': self.width,
            'height': self.height,
            'fps': self.fps
        }
    
    def cleanup(self):
        """Close video file."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.frame_generator = None
        self.current_frame = None
        self.last_frame_time = None

