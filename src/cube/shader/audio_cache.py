"""Audio cache for pre-extracted video audio tracks.

Maintains a small LRU cache of extracted audio files for instant playback.
"""

import os
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional

try:
    from moviepy.editor import VideoFileClip

    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class AudioCache:
    """Thread-safe cache for pre-extracted video audio files.

    Uses LRU eviction to maintain a fixed number of cached audio files.
    """

    def __init__(self, max_size: int = 3) -> None:
        """Initialize audio cache.

        Args:
            max_size: Maximum number of audio files to cache.
        """
        self.max_size = max_size
        self.cache: "OrderedDict[str, str]" = OrderedDict()
        self.lock = threading.Lock()
        self.extraction_threads: Dict[str, threading.Thread] = {}

    def get(self, video_path: str) -> Optional[str]:
        """Get cached audio file path for a video.

        Args:
            video_path: Path to video file.

        Returns:
            Path to extracted audio file, or None if not cached.
        """
        with self.lock:
            if video_path in self.cache:
                # Move to end to mark as recently used
                self.cache.move_to_end(video_path)
                return self.cache[video_path]
        return None

    def is_extracting(self, video_path: str) -> bool:
        """Check if audio is currently being extracted for a video."""
        with self.lock:
            thread = self.extraction_threads.get(video_path)
            return thread is not None and thread.is_alive()

    def extract_async(self, video_path: str) -> None:
        """Start extracting audio for a video in the background.

        Args:
            video_path: Path to video file.
        """
        if not MOVIEPY_AVAILABLE:
            # Nothing to do if moviepy is not installed
            return

        with self.lock:
            if video_path in self.cache:
                return
            if video_path in self.extraction_threads and self.extraction_threads[video_path].is_alive():
                return

            thread = threading.Thread(
                target=self._extract_audio,
                args=(video_path,),
                daemon=True,
            )
            self.extraction_threads[video_path] = thread

        thread.start()

    def _extract_audio(self, video_path: str) -> None:
        """Extract audio from video (runs in background thread)."""
        try:
            if not MOVIEPY_AVAILABLE:
                return

            clip = VideoFileClip(video_path)
            if clip.audio is None:
                clip.close()
                return

            # Create a temporary WAV file
            temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            audio_file = temp_audio.name
            temp_audio.close()

            # Write audio track to file
            clip.audio.write_audiofile(audio_file, verbose=False, logger=None)
            clip.close()

            with self.lock:
                # Evict least recently used items if over capacity
                while len(self.cache) >= self.max_size:
                    old_video_path, old_audio_file = self.cache.popitem(last=False)
                    try:
                        os.unlink(old_audio_file)
                    except Exception:
                        pass

                self.cache[video_path] = audio_file
        except Exception as e:
            print(f"❌ Audio extraction failed for {Path(video_path).name}: {e}")
        finally:
            with self.lock:
                self.extraction_threads.pop(video_path, None)

    def clear(self) -> None:
        """Clear all cached audio files."""
        with self.lock:
            for audio_file in self.cache.values():
                try:
                    os.unlink(audio_file)
                except Exception:
                    pass
            self.cache.clear()

    def __len__(self) -> int:
        """Get number of cached audio files."""
        with self.lock:
            return len(self.cache)

