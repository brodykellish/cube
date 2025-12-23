# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/video_frame_buffer.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-14 03:27:04 UTC (1765682824)

"""
Thread-safe ring buffer for decoded video frames.

Allows background thread to decode frames while main thread renders.
"""
import threading
import numpy as np
from collections import deque
from typing import Optional

class VideoFrameBuffer:
    """
    Thread-safe ring buffer for video frames.

    Producer (decoder thread) adds frames.
    Consumer (render thread) retrieves latest frame.
    """

    def __init__(self, buffer_size: int=3):
        """
        Initialize frame buffer.

        Args:
            buffer_size: Number of frames to buffer (3-5 recommended)
        """
        self.buffer_size = buffer_size
        self.frames = deque(maxlen=buffer_size)
        self.lock = threading.Lock()
        self.last_frame = None
        self.frame_count = 0

    def put_frame(self, frame: np.ndarray):
        """
        Add a decoded frame to the buffer (called by decoder thread).

        Args:
            frame: RGB frame data (H, W, 3) as uint8 numpy array
        """
        with self.lock:
            self.frames.append(frame.copy())
            self.frame_count += 1

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest available frame (called by render thread).

        Returns:
            Latest frame, or last known frame if buffer empty, or None
        """
        with self.lock:
            if len(self.frames) > 0:
                self.last_frame = self.frames[-1]
                return self.last_frame
            return self.last_frame

    def clear(self):
        """Clear all buffered frames."""
        with self.lock:
            self.frames.clear()
            self.last_frame = None

    def get_buffer_fill(self) -> float:
        """
        Get buffer fill ratio (0.0 = empty, 1.0 = full).

        Returns:
            Fill ratio
        """
        with self.lock:
            return len(self.frames) / self.buffer_size if self.buffer_size > 0 else 0.0

    def __len__(self) -> int:
        """Get current number of frames in buffer."""
        with self.lock:
            return len(self.frames)