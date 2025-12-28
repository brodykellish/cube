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
        self.video_start_time = None  # Track when video playback started
        self.total_frames = 0
        
        # Debug tracking for actual FPS
        self._frame_advance_count = 0
        self._first_advance_time = None
        self._last_log_time = None
        self._log_interval = 2.0  # Log every 2 seconds
        
        # Performance tracking
        self._frame_load_times = []  # Track time to load each frame
        self._max_load_time_samples = 10  # Keep last N samples
        
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
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            print(f'Video loaded: {self.file_path.name}')
            print(f'  Resolution: {self.width}×{self.height}')
            print(f'  FPS: {self.fps:.1f}')
            print(f'  Total frames: {self.total_frames}')
            print(f'  Duration: {self.total_frames / self.fps:.1f}s')
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
                # Optimize: do color conversion and flip in one pass if possible
                # BGR to RGB conversion
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Flip vertically (OpenGL coordinate system)
                frame = cv2.flip(frame, 0)
                # Ensure contiguous array (required for some operations)
                if not frame.flags['C_CONTIGUOUS']:
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
        
        # Initialize video playback timeline on first call
        if self.video_start_time is None:
            self.video_start_time = t
            self.last_frame_time = 0.0  # Start at 0 relative to video start
            self.frame_generator = self.frames()
            self._first_advance_time = None  # Reset FPS tracking
            self._frame_advance_count = 0
            # Pre-load first frame immediately
            try:
                frame = next(self.frame_generator)
                if frame is not None:
                    self.current_frame = frame
            except StopIteration:
                pass
        
        # Calculate video playback time (relative to when video started)
        video_time = t - self.video_start_time
        
        # Check if enough time has passed to advance to next frame
        time_since_last_frame = video_time - self.last_frame_time
        should_advance = time_since_last_frame >= self.frame_duration
        
        # If we've fallen significantly behind, catch up by advancing multiple frames
        # This handles cases where the render loop might skip frames or have timing variations
        frames_to_advance = 1
        if should_advance and time_since_last_frame > self.frame_duration * 1.5:
            # Calculate how many frames we should have advanced
            frames_to_advance = int(time_since_last_frame / self.frame_duration)
            # Cap at reasonable limit to avoid huge jumps
            frames_to_advance = min(frames_to_advance, 10)
        
        if should_advance:
            # Advance frame(s) - track loading time
            import time as time_module
            load_start = time_module.time()
            
            # Advance the calculated number of frames (catch up if behind)
            frame = None
            try:
                for _ in range(frames_to_advance):
                    try:
                        frame = next(self.frame_generator)
                        if frame is None:
                            break
                    except StopIteration:
                        # Video ended, restart if looping
                        if self.loop:
                            # Reset video timeline for new loop
                            self.video_start_time = t
                            self.last_frame_time = 0.0
                            self._first_advance_time = None
                            self._frame_advance_count = 0
                            self.frame_generator = self.frames()
                            try:
                                frame = next(self.frame_generator)
                            except StopIteration:
                                frame = None
                        else:
                            frame = None
                        break
            except Exception as e:
                print(f'[VideoFileFrameLoader] Error advancing frame: {e}')
                frame = None
            
            load_time = time_module.time() - load_start
            
            # Track load times for performance analysis
            if load_time > 0 and frames_to_advance > 0:
                self._frame_load_times.append(load_time / frames_to_advance)  # Average per frame
                if len(self._frame_load_times) > self._max_load_time_samples:
                    self._frame_load_times.pop(0)
            
            if frame is not None:
                self.current_frame = frame
                # Update last_frame_time based on how many frames we advanced
                # This prevents time from being "lost" when catching up
                self.last_frame_time = self.last_frame_time + (frames_to_advance * self.frame_duration)
                
                # Track frame advancement for FPS calculation
                self._frame_advance_count += frames_to_advance
                if self._first_advance_time is None:
                    self._first_advance_time = video_time
                    self._last_log_time = video_time
                
                # Log actual FPS periodically with performance stats
                if self._last_log_time is not None and (video_time - self._last_log_time) >= self._log_interval:
                    elapsed = video_time - self._first_advance_time
                    if elapsed > 0:
                        actual_fps = self._frame_advance_count / elapsed
                        avg_load_time = sum(self._frame_load_times) / len(self._frame_load_times) if self._frame_load_times else 0
                        max_load_time = max(self._frame_load_times) if self._frame_load_times else 0
                        print(f'[VideoFileFrameLoader] Actual FPS: {actual_fps:.2f} (target: {self.fps:.2f}, frames: {self._frame_advance_count}, time: {video_time:.2f}s, load: {avg_load_time*1000:.1f}ms avg, {max_load_time*1000:.1f}ms max)')
                    self._last_log_time = video_time
                
                return frame
            else:
                # No frame available, might have hit end of video
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


class RecursiveVideoDirectoryFrameLoader(FrameLoader):
    """Loads frames from all videos in a directory and subdirectories, playing them in sequence."""
    
    def __init__(self, directory_path: Path, loop: bool = True):
        """
        Initialize recursive video directory frame loader.
        
        Args:
            directory_path: Path to directory containing videos
            loop: Whether to loop back to first video when all videos finish
        """
        if not CV2_AVAILABLE:
            raise RuntimeError('opencv-python is required for video support')
        
        self.directory_path = Path(directory_path)
        if not self.directory_path.exists() or not self.directory_path.is_dir():
            raise FileNotFoundError(f'Directory not found: {directory_path}')
        
        self.loop = loop
        self.video_files = []
        self.current_video_index = 0
        self.current_video_loader: Optional[VideoFileFrameLoader] = None
        self.width = 0
        self.height = 0
        self.fps = 30.0
        self.frame_duration = None
        self.current_frame = None
        self.last_frame_time = None
        self.video_start_time: Optional[float] = None  # Track when video playback started (for entire sequence)
        self.current_video_start_time: Optional[float] = None  # Track when current video started
        self.has_received_frame = False  # Track if we've gotten at least one frame from current video
        
        self._load_all_videos()
        if not self.video_files:
            raise FileNotFoundError(f'No video files found in {directory_path} or subdirectories')
        
        # Load first video to get dimensions
        self._load_video(0)
        
        # Calculate frame duration from FPS
        self.frame_duration = 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0
        
        print(f'Loaded {len(self.video_files)} videos from {directory_path} (recursive)')
    
    def _load_all_videos(self):
        """Recursively find all video files in directory and subdirectories."""
        video_extensions = ['.mp4', '.MP4', '.mov', '.MOV', '.avi', '.AVI', '.mkv', '.MKV', '.webm', '.WEBM', '.m4v', '.M4V']
        
        for ext in video_extensions:
            # Find all videos recursively
            self.video_files.extend(self.directory_path.rglob(f'*{ext}'))
        
        # Sort by path for consistent ordering
        self.video_files = sorted(set(self.video_files), key=lambda x: str(x))
    
    def _load_video(self, index: int):
        """Load video at specified index."""
        if index < 0 or index >= len(self.video_files):
            if self.loop:
                index = index % len(self.video_files)
            else:
                raise IndexError(f'Video index {index} out of range')
        
        self.current_video_index = index
        
        # Cleanup previous video loader
        if self.current_video_loader is not None:
            self.current_video_loader.cleanup()
        
        # Create new loader for this video
        video_path = self.video_files[index]
        self.current_video_loader = VideoFileFrameLoader(video_path, loop=False)
        
        # Get properties from current video
        props = self.current_video_loader.get_properties()
        self.width = props['width']
        self.height = props['height']
        self.fps = props['fps']
        self.frame_duration = 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0
        
        # Reset tracking for new video
        self.has_received_frame = False
        self.current_video_start_time = None
        
        print(f'Video {index + 1}/{len(self.video_files)}: {video_path.relative_to(self.directory_path)}')
    
    def frames(self) -> Iterator[np.ndarray]:
        """
        Generator that yields frames from all videos in sequence.
        
        Yields:
            RGB frame as numpy array (H, W, 3) with dtype uint8
        """
        while True:
            if self.current_video_loader is None:
                break
            
            # Get frames from current video
            frame_generator = self.current_video_loader.frames()
            for frame in frame_generator:
                yield frame
            
            # Current video finished, move to next
            next_index = self.current_video_index + 1
            if next_index >= len(self.video_files):
                if self.loop:
                    next_index = 0
                else:
                    break
            
            self._load_video(next_index)
    
    def get_current_frame(self, t: float) -> Optional[np.ndarray]:
        """
        Get the current frame based on time, respecting video FPS.
        
        Automatically advances to next video when current video finishes.
        
        Args:
            t: Current time in seconds
            
        Returns:
            Current frame as numpy array (H, W, 3) with dtype uint8, or None
        """
        if self.current_video_loader is None:
            return None
        
        # Initialize video playback time on first call
        if self.video_start_time is None:
            self.video_start_time = t
            self.last_frame_time = 0.0
        
        # Calculate video playback time (relative to when sequence started)
        video_time = t - self.video_start_time
        
        # Get frame from current video (pass absolute time, loader handles its own timing)
        frame = self.current_video_loader.get_current_frame(t)
        
        # Track if we've received at least one frame from this video
        if frame is not None:
            self.has_received_frame = True
        
        # Only advance to next video if:
        # 1. We've received at least one frame from the current video (video has started)
        # 2. We're now getting None (video has finished)
        if frame is None and self.has_received_frame:
            # Video has finished, advance to next
            next_index = self.current_video_index + 1
            if next_index < len(self.video_files) or self.loop:
                if next_index >= len(self.video_files):
                    next_index = 0
                    # If looping back to start, reset video start time
                    if self.loop:
                        self.video_start_time = t
                        self.last_frame_time = 0.0
                self._load_video(next_index)
                # Get first frame from new video
                frame = self.current_video_loader.get_current_frame(t)
                if frame is not None:
                    self.has_received_frame = True
            else:
                # No more videos and not looping
                return None
        
        return frame
    
    def get_properties(self) -> dict:
        """Get video properties from current video."""
        if self.current_video_loader:
            return self.current_video_loader.get_properties()
        return {
            'width': self.width,
            'height': self.height,
            'fps': self.fps
        }
    
    def cleanup(self):
        """Clean up all video resources."""
        if self.current_video_loader is not None:
            self.current_video_loader.cleanup()
            self.current_video_loader = None
        self.video_files.clear()
        self.current_frame = None
        self.last_frame_time = None

