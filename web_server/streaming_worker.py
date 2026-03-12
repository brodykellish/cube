"""
Streaming Worker for LED Cube Visualization.

Consumes framebuffers from the visualization renderer and streams them
to web clients via WebSocket using MJPEG encoding.

Target: 60 FPS with 150-250ms latency for live performance feedback.
"""

import threading
import queue
import time
from io import BytesIO
from typing import Optional
import base64

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("[StreamingWorker] Warning: Pillow not available, streaming disabled")


class StreamingWorker:
    """
    Worker thread that consumes framebuffers and streams them via WebSocket.

    Architecture:
    - Runs in separate thread to avoid blocking visualization rendering
    - Reads frames from visualization's framebuffer_queue (non-blocking)
    - Encodes frames as JPEG for bandwidth efficiency
    - Broadcasts to all connected WebSocket clients via SocketIO

    Performance:
    - Target: 60 FPS stream rate
    - JPEG quality: 80 (balance quality vs bandwidth)
    - Frame size: ~40-80 KB per frame at 384x64 resolution
    - Expected bandwidth: 2-4 Mbps
    - Expected latency: 150-250ms (100-180ms on LAN)
    """

    def __init__(
        self,
        framebuffer_queue: queue.Queue,
        socketio,
        target_fps: int = 60,
        jpeg_quality: int = 95
    ):
        """
        Initialize streaming worker.

        Args:
            framebuffer_queue: Queue providing framebuffers from renderer
            socketio: Flask-SocketIO instance for WebSocket broadcasting
            target_fps: Target streaming frame rate (default: 60)
            jpeg_quality: JPEG encoding quality 0-100 (default: 95)
        """
        if not PILLOW_AVAILABLE:
            raise ImportError("Pillow required for streaming. Install with: pip install Pillow")

        self.framebuffer_queue = framebuffer_queue
        self.socketio = socketio
        self.target_fps = target_fps
        self.jpeg_quality = jpeg_quality

        self.stop_flag = threading.Event()
        self.thread: Optional[threading.Thread] = None

        # Statistics
        self.frames_sent = 0
        self.bytes_sent = 0
        self.last_stats_time = time.time()
        self.dropped_frames = 0

        # Performance tracking
        self.encoding_times = []
        self.emit_times = []

    def start(self):
        """Start the streaming worker thread."""
        if self.thread and self.thread.is_alive():
            print("[StreamingWorker] Already running")
            return

        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="StreamingWorker")
        self.thread.start()
        print(f"[StreamingWorker] Started (target: {self.target_fps} FPS, quality: {self.jpeg_quality})")

    def stop(self):
        """Stop the streaming worker thread."""
        if not self.thread or not self.thread.is_alive():
            return

        print("[StreamingWorker] Stopping...")
        self.stop_flag.set()

        if self.thread:
            self.thread.join(timeout=2.0)

        print("[StreamingWorker] Stopped")

    def _run(self):
        """Main streaming loop."""
        frame_time = 1.0 / self.target_fps

        while not self.stop_flag.is_set():
            loop_start = time.time()

            try:
                # Get latest frame (non-blocking)
                # Drop older frames to maintain low latency
                framebuffer = None
                dropped = 0

                # Drain queue to get most recent frame
                while True:
                    try:
                        framebuffer = self.framebuffer_queue.get_nowait()
                        if dropped > 0:
                            self.dropped_frames += 1
                        dropped += 1
                    except queue.Empty:
                        break

                if framebuffer is None:
                    # No frame available - renderer might be slower than target FPS
                    time.sleep(frame_time / 2)
                    continue

                # Encode as JPEG
                encode_start = time.time()
                jpeg_data = self._encode_frame(framebuffer)
                encode_time = time.time() - encode_start
                self.encoding_times.append(encode_time)

                # Emit to all connected clients
                emit_start = time.time()
                self._emit_frame(jpeg_data)
                emit_time = time.time() - emit_start
                self.emit_times.append(emit_time)

                # Update stats
                self.frames_sent += 1
                self.bytes_sent += len(jpeg_data)

                # Trim performance tracking arrays
                if len(self.encoding_times) > 100:
                    self.encoding_times = self.encoding_times[-100:]
                if len(self.emit_times) > 100:
                    self.emit_times = self.emit_times[-100:]

            except Exception as e:
                print(f"[StreamingWorker] Error in streaming loop: {e}")
                import traceback
                traceback.print_exc()

            # FPS limiting
            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _encode_frame(self, framebuffer) -> bytes:
        """
        Encode framebuffer as JPEG.

        Args:
            framebuffer: numpy array (H, W, 3) uint8 RGB

        Returns:
            JPEG-encoded bytes
        """
        # Convert numpy array to PIL Image
        image = Image.fromarray(framebuffer, mode='RGB')

        # Encode as JPEG
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=self.jpeg_quality, optimize=True)
        jpeg_data = buffer.getvalue()

        return jpeg_data

    def _emit_frame(self, jpeg_data: bytes):
        """
        Emit frame to all connected WebSocket clients.

        Args:
            jpeg_data: JPEG-encoded frame bytes
        """
        # Encode as base64 for JSON transport
        jpeg_base64 = base64.b64encode(jpeg_data).decode('ascii')

        # Emit to all clients on default namespace
        self.socketio.emit(
            'video_frame',
            {
                'data': jpeg_base64,
                'timestamp': time.time(),
                'format': 'jpeg'
            }
        )

    def get_stats(self) -> dict:
        """
        Get streaming statistics.

        Returns:
            Dictionary with FPS, bandwidth, latency estimates
        """
        now = time.time()
        elapsed = now - self.last_stats_time

        if elapsed < 0.1:
            elapsed = 0.1  # Avoid division by zero

        fps = self.frames_sent / elapsed if elapsed > 0 else 0
        bandwidth_mbps = (self.bytes_sent * 8 / 1_000_000) / elapsed if elapsed > 0 else 0

        # Calculate average encoding and emit times
        avg_encode_ms = sum(self.encoding_times) / len(self.encoding_times) * 1000 if self.encoding_times else 0
        avg_emit_ms = sum(self.emit_times) / len(self.emit_times) * 1000 if self.emit_times else 0

        stats = {
            'fps': round(fps, 1),
            'bandwidth_mbps': round(bandwidth_mbps, 2),
            'frames_sent': self.frames_sent,
            'dropped_frames': self.dropped_frames,
            'avg_encode_ms': round(avg_encode_ms, 2),
            'avg_emit_ms': round(avg_emit_ms, 2),
            'total_latency_ms': round(avg_encode_ms + avg_emit_ms, 2),
            'target_fps': self.target_fps,
            'jpeg_quality': self.jpeg_quality
        }

        return stats

    def reset_stats(self):
        """Reset statistics counters."""
        self.frames_sent = 0
        self.bytes_sent = 0
        self.dropped_frames = 0
        self.last_stats_time = time.time()
        self.encoding_times.clear()
        self.emit_times.clear()

    def set_quality(self, quality: int):
        """
        Update JPEG encoding quality.

        Args:
            quality: JPEG quality 0-100
        """
        self.jpeg_quality = max(0, min(100, quality))
        print(f"[StreamingWorker] Quality set to {self.jpeg_quality}")

    def set_target_fps(self, fps: int):
        """
        Update target streaming FPS.

        Args:
            fps: Target FPS (10-120)
        """
        self.target_fps = max(10, min(120, fps))
        print(f"[StreamingWorker] Target FPS set to {self.target_fps}")

    def is_running(self) -> bool:
        """Check if streaming worker is running."""
        return self.thread is not None and self.thread.is_alive()

    def __repr__(self) -> str:
        status = "running" if self.is_running() else "stopped"
        return f"StreamingWorker({status}, {self.target_fps} FPS, Q{self.jpeg_quality})"
