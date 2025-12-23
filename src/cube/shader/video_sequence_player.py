# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/video_sequence_player.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-22 20:44:34 UTC (1766436274)

"""
Video Sequence Player - plays multiple videos in sequence with looping.

Manages a directory of videos and plays them one after another, looping
back to the first video when the last one finishes.
"""
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np

try:
    import cv2  # type: ignore[import-untyped]

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from .uniform_sources import UniformSource
from .video_uniform_source import VideoUniformSource
from .audio_cache import AudioCache

class VideoSequencePlayer(UniformSource):
    """
    Plays a sequence of videos in a directory, looping infinitely.
    """

    def __init__(self, directory_path: str, loop: bool=True, buffer_size: int=3, enable_audio: bool=True):
        """
        Initialize video sequence player with threaded decoding and audio.

        Args:
            directory_path: Path to directory containing video files
            loop: Whether to loop back to first video when sequence ends
            buffer_size: Frame buffer size for background decoding
            enable_audio: Whether to enable audio playback
        """
        if not CV2_AVAILABLE:
            raise RuntimeError('opencv-python is required for video support')
        self.directory_path = Path(directory_path)
        if not self.directory_path.exists() or not self.directory_path.is_dir():
            raise FileNotFoundError(f'Directory not found: {directory_path}')
        self.loop = loop
        self.buffer_size = buffer_size
        self.enable_audio = enable_audio
        self.video_files: list[Path] = []
        self.current_video_index = 0
        self.current_video_source: Optional[VideoUniformSource] = None
        self.audio_cache = AudioCache(max_size=3) if enable_audio else None
        self._load_video_files()
        if not self.video_files:
            raise FileNotFoundError(f'No video files found in {directory_path}')
        if self.audio_cache:
            print('🔊 Extracting audio for first video...')
            first_video_path = str(self.video_files[0])
            self.audio_cache._extract_audio(first_video_path)
            for i in range(1, min(3, len(self.video_files))):
                self.audio_cache.extract_async(str(self.video_files[i]))
        self._load_video(0)
        print(f'Video sequence player initialized: {len(self.video_files)} videos')
        for i, video in enumerate(self.video_files, 1):
            print(f'  {i}. {video.name}')

    def _load_video_files(self) -> None:
        """Load all video files from directory."""
        self.video_files = []
        for ext in ['mp4', 'MP4', 'mov', 'MOV', 'avi', 'AVI', 'mkv', 'MKV']:
            self.video_files.extend(self.directory_path.glob(f'*.{ext}'))
        self.video_files = sorted(set(self.video_files), key=lambda x: x.name)

    def _load_video(self, index: int) -> None:
        """Load video at specified index with threaded decoding and cached audio."""
        if index < 0 or index >= len(self.video_files):
            if self.loop:
                index = index % len(self.video_files)
            else:
                raise IndexError(f'Video index {index} out of range')
        self.current_video_index = index
        video_path = self.video_files[index]
        if self.current_video_source is not None:
            self.current_video_source.cleanup()
        cached_audio_path: Optional[str] = None
        if self.audio_cache:
            cached_audio_path = self.audio_cache.get(str(video_path))
        self.current_video_source = VideoUniformSource.from_file(
            str(video_path),
            loop=False,
            buffer_size=self.buffer_size,
            enable_audio=self.enable_audio,
            audio_file_path=cached_audio_path,
        )
        print(f'Video {index + 1}/{len(self.video_files)}: {video_path.name}')
        if self.audio_cache:
            for offset in range(1, 4):
                future_index = (index + offset) % len(self.video_files)
                future_video_path = str(self.video_files[future_index])
                self.audio_cache.extract_async(future_video_path)

    def _check_and_advance_video(self) -> None:
        """Check if current video has finished, advance to next if so."""
        if self.current_video_source is None:
            return
        from .video_uniform_source import VideoFileFrameReader

        if isinstance(self.current_video_source.frame_reader, VideoFileFrameReader):
            cap = self.current_video_source.frame_reader.get_cap()
            if cap is not None:
                current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                total_frames = self.current_video_source.total_frames
                if current_frame >= total_frames - 1:
                    next_index = self.current_video_index + 1
                    if next_index >= len(self.video_files) and self.loop:
                        next_index = 0
                    else:
                        return
                    self._load_video(next_index)

    def update(self, dt: float) -> None:
        """
        Update video playback.

        Args:
            dt: Delta time since last update
        """
        if self.current_video_source is None:
            return
        self.current_video_source.update(dt)
        self._check_and_advance_video()

    def get_uniforms(self) -> Dict[str, Any]:
        """Get uniforms from current video source."""
        if self.current_video_source is None:
            return {}
        uniforms = self.current_video_source.get_uniforms()
        uniforms['iVideoIndex'] = float(self.current_video_index)
        uniforms['iVideoCount'] = float(len(self.video_files))
        return uniforms

    def get_frame_data(self) -> Optional[np.ndarray]:
        """Get current frame data from active video source."""
        if self.current_video_source is None:
            return None
        return self.current_video_source.get_frame_data()

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.current_video_source is not None:
            self.current_video_source.cleanup()
            self.current_video_source = None
        if self.audio_cache is not None:
            self.audio_cache.clear()

    def reset(self) -> None:
        """Reset to first video."""
        self._load_video(0)

    def toggle_audio(self):
        """Toggle audio mute/unmute for current video."""
        if self.current_video_source is not None:
            return self.current_video_source.toggle_audio()
        return None

    def is_audio_muted(self) -> bool:
        """Check if audio is muted."""
        if self.current_video_source is not None:
            return self.current_video_source.is_audio_muted()
        return False