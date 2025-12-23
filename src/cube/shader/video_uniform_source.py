# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: /Users/brody/k/nye/cube/src/cube/shader/video_uniform_source.py
# Bytecode version: 3.12.0rc2 (3531)
# Source timestamp: 2025-12-23 02:46:37 UTC (1766457997)

"""\nVideo Uniform Source - provides video frames as shader textures.\n\nDecodes video files on-the-fly using OpenCV with background threading for smooth playback.\n"""
import time
import threading
import tempfile
import numpy as np
from typing import Dict, Any, Optional, List
from pathlib import Path
from abc import ABC, abstractmethod
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    pass  # postinserted
else:  # inserted
    try:
        import pygame
        PYGAME_AVAILABLE = True
except ImportError as e:
    else:  # inserted
        try:
            from moviepy import VideoFileClip
            MOVIEPY_AVAILABLE = True
    except ImportError:
        else:  # inserted
            try:
                import sounddevice as sd
                SOUNDDEVICE_AVAILABLE = True
        except ImportError:
            else:  # inserted
                from .uniform_sources import UniformSource
                from .video_frame_buffer import VideoFrameBuffer

                class FrameReader(ABC):
                    """Abstract base for frame readers (video files, webcam, etc.)"""

                    @abstractmethod
                    def open(self) -> bool:
                        """Open the frame source. Returns True if successful."""  # inserted
                        return

                    @abstractmethod
                    def read_frame(self) -> Optional[np.ndarray]:
                        """Read next frame. Returns RGB array (H, W, 3) or None if no frame."""  # inserted
                        return

                    @abstractmethod
                    def get_properties(self) -> Dict[str, Any]:
                        """Get frame source properties (width, height, fps, etc.)"""  # inserted
                        return

                    @abstractmethod
                    def has_audio(self) -> bool:
                        """Check if this frame source has audio capability."""  # inserted
                        return

                    @abstractmethod
                    def start_audio(self) -> bool:
                        """Start audio capture/playback. Returns True if successful."""  # inserted
                        return

                    @abstractmethod
                    def stop_audio(self):
                        """Stop audio capture/playback."""  # inserted
                        return

                    @abstractmethod
                    def cleanup(self):
                        """Close the frame source."""  # inserted
                        return

                class VideoFileFrameReader(FrameReader):
                    """Reads frames from a video file."""

                    def __init__(self, video_path: Path, loop: bool=True):
                        if not CV2_AVAILABLE:
                            raise RuntimeError('opencv-python is required for video support')
                        self.video_path = Path(video_path)
                        if not self.video_path.exists():
                            raise FileNotFoundError(f'Video file not found: {video_path}')
                        self.loop = loop
                        self.cap = None
                        self.width = 0
                        self.height = 0
                        self.fps = 30.0
                        self.total_frames = 0
                        self.audio_file = None
                        self.audio_file_owned = True
                        self.audio_initialized = False
                        self.audio_ready = False
                        self.audio_start_time = None
                        self.audio_extraction_thread = None
                        self.enable_audio = PYGAME_AVAILABLE and MOVIEPY_AVAILABLE

                    def open(self) -> bool:
                        """Open video file with OpenCV."""  # inserted
                        try:
                            self.cap = cv2.VideoCapture(str(self.video_path))
                            if not self.cap.isOpened():
                                raise RuntimeError(f'Failed to open video: {self.video_path}')
                            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                            if self.fps <= 0:
                                self.fps = 30.0
                            print(f'Video loaded: {self.video_path.name}')
                            print(f'  Resolution: {self.width}×{self.height}')
                            print(f'  FPS: {self.fps:.1f}')
                            print(f'  Total frames: {self.total_frames}')
                            print(f'  Duration: {self.total_frames / self.fps:.1f}s')
                            return True
                        except Exception as e:
                            print(f'Error opening video: {e}')
                            return False
                        else:  # inserted
                            pass

                    def read_frame(self) -> Optional[np.ndarray]:
                        """Read next frame from video, with looping support."""  # inserted
                        if self.cap is None:
                            return
                        ret, frame = self.cap.read()
                        if not ret:
                            if self.loop:
                                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                ret, frame = self.cap.read()
                            else:  # inserted
                                return None
                        if ret:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame = cv2.flip(frame, 0)
                            frame = np.ascontiguousarray(frame, dtype=np.uint8)
                            return frame
                        return None

                    def get_properties(self) -> Dict[str, Any]:
                        """Get video properties."""  # inserted
                        return {'width': self.width, 'height': self.height, 'fps': self.fps, 'total_frames': self.total_frames}

                    def has_audio(self) -> bool:
                        """Video files may have audio."""  # inserted
                        return self.enable_audio

                    def start_audio(self) -> bool:
                        """Extract and play audio from video file."""  # inserted
                        if not self.enable_audio:
                            return False
                        self.audio_file_owned = True
                        self.audio_extraction_thread = threading.Thread(target=self._extract_and_play_audio, daemon=True)
                        self.audio_extraction_thread.start()
                        return True

                    def _extract_and_play_audio(self):
                        """Extract audio from video and start playback."""  # inserted
                        try:
                            clip = VideoFileClip(str(self.video_path))
                            if clip.audio is None:
                                self.enable_audio = False
                                clip.close()
                                return
                            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                            self.audio_file = temp_audio.name
                            temp_audio.close()
                            clip.audio.write_audiofile(self.audio_file)
                            clip.close()
                            print(f'🔊 Audio extracted: {self.video_path.name}')
                            self._play_audio()
                        except Exception as e:
                            print(f'❌ Audio extraction failed: {e}')
                            self.enable_audio = False
                            self.audio_ready = False
                            return

                    def _play_audio(self):
                        """Play already-extracted audio file."""  # inserted
                        try:
                            if not self.audio_initialized:
                                if not pygame.mixer.get_init():
                                    pygame.mixer.init()
                                self.audio_initialized = True
                            pygame.mixer.music.load(self.audio_file)
                            pygame.mixer.music.play(loops=(-1) if self.loop else 0)
                            self.audio_start_time = time.time()
                            if pygame.mixer.music.get_busy():
                                self.audio_ready = True
                            else:  # inserted
                                print('⚠️  Audio loaded but not playing')
                                self.audio_ready = False
                        except Exception as e:
                            print(f'❌ Failed to play audio: {e}')
                            self.enable_audio = False
                            self.audio_ready = False

                    def stop_audio(self):
                        """Stop audio playback."""  # inserted
                        if self.enable_audio and self.audio_initialized:
                            try:
                                pygame.mixer.music.stop()
                                pygame.mixer.music.unload()
                            except Exception:
                                pass  # postinserted
                            return None
                        else:  # inserted
                            pass

                    def cleanup(self):
                        """Close video file and clean up audio."""  # inserted
                        if self.audio_extraction_thread is not None and self.audio_extraction_thread.is_alive():
                            print('   Waiting for audio extraction to complete...')
                            self.audio_extraction_thread.join(timeout=2.0)
                        self.stop_audio()
                        if self.audio_file is not None and self.audio_file_owned:
                            try:
                                import os
                                os.unlink(self.audio_file)
                            except Exception:
                                pass  # postinserted
                        else:  # inserted
                            pass  # postinserted
                        if self.cap is not None:
                            self.cap.release()
                            self.cap = None
                        self.audio_ready = False
                        self.audio_start_time = None
                                pass
                            else:  # inserted
                                pass

                    def get_cap(self):
                        """Get the OpenCV VideoCapture object (for frame position tracking)."""  # inserted
                        return self.cap

                    def set_frame_position(self, frame: int):
                        """Set video frame position (for seeking)."""  # inserted
                        if self.cap is not None:
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)

                class VideoDirectoryFrameReader(FrameReader):
                    """Reads frames from a directory of video files, playing them in sequence."""

                    def __init__(self, directory_path: Path, loop: bool=True):
                        if not CV2_AVAILABLE:
                            raise RuntimeError('opencv-python is required for video support')
                        self.directory_path = Path(directory_path)
                        if not self.directory_path.exists() or not self.directory_path.is_dir():
                            raise FileNotFoundError(f'Directory not found: {directory_path}')
                        self.loop = loop
                        self.video_files = []
                        self.current_video_index = 0
                        self.current_reader = None
                        self._load_video_files()
                        if not self.video_files:
                            raise FileNotFoundError(f'No video files found in {directory_path}')

                    def _load_video_files(self):
                        """Load all video files from directory."""  # inserted
                        self.video_files = []
                        for ext in ['mp4', 'MP4', 'mov', 'MOV', 'avi', 'AVI', 'mkv', 'MKV']:
                            self.video_files.extend(self.directory_path.glob(f'*.{ext}'))
                        self.video_files = sorted(set(self.video_files), key=lambda x: x.name)

                    def _load_video(self, index: int):
                        """Load video at specified index."""  # inserted
                        if index < 0 or index >= len(self.video_files):
                            if self.loop:
                                index = index % len(self.video_files)
                            else:  # inserted
                                raise IndexError(f'Video index {index} out of range')
                        self.current_video_index = index
                        video_path = self.video_files[index]
                        if self.current_reader is not None:
                            self.current_reader.cleanup()
                        self.current_reader = VideoFileFrameReader(video_path, loop=False)
                        if not self.current_reader.open():
                            raise RuntimeError(f'Failed to open video: {video_path}')
                        print(f'Video {index + 1}/{len(self.video_files)}: {video_path.name}')

                    def open(self) -> bool:
                        """Open first video in directory."""  # inserted
                        try:
                            self._load_video(0)
                            return True
                        except Exception as e:
                            print(f'Error opening video directory: {e}')
                            return False
                        else:  # inserted
                            pass

                    def read_frame(self) -> Optional[np.ndarray]:
                        """Read next frame, advancing to next video when current one ends."""  # inserted
                        if self.current_reader is None:
                            return
                        frame = self.current_reader.read_frame()
                        if frame is None:
                            next_index = self.current_video_index + 1
                            if next_index >= len(self.video_files):
                                if self.loop:
                                    next_index = 0
                                else:  # inserted
                                    return None
                            self._load_video(next_index)
                            frame = self.current_reader.read_frame()
                        return frame

                    def get_properties(self) -> Dict[str, Any]:
                        """Get properties from current video."""  # inserted
                        if self.current_reader is None:
                            return {'width': 0, 'height': 0, 'fps': 30.0, 'total_frames': 0}
                        props = self.current_reader.get_properties()
                        props['video_index'] = self.current_video_index
                        props['video_count'] = len(self.video_files)
                        return props

                    def has_audio(self) -> bool:
                        """Video files may have audio."""  # inserted
                        return self.current_reader.has_audio() if self.current_reader else False

                    def start_audio(self) -> bool:
                        """Start audio for current video."""  # inserted
                        if self.current_reader is None:
                            return False
                        return self.current_reader.start_audio()

                    def stop_audio(self):
                        """Stop audio for current video."""  # inserted
                        if self.current_reader is not None:
                            self.current_reader.stop_audio()

                    def cleanup(self):
                        """Close current video and clean up."""  # inserted
                        if self.current_reader is not None:
                            self.current_reader.cleanup()
                            self.current_reader = None

                class WebcamFrameReader(FrameReader):
                    """Reads frames from a webcam."""

                    def __init__(self, device_index: int=0):
                        if not CV2_AVAILABLE:
                            raise RuntimeError('opencv-python is required for webcam support')
                        self.device_index = device_index
                        self.cap = None
                        self.width = 0
                        self.height = 0
                        self.fps = 30.0
                        self.audio_stream = None
                        self.audio_initialized = False
                        self.audio_ready = False
                        self.enable_audio = PYGAME_AVAILABLE and SOUNDDEVICE_AVAILABLE
                        self.audio_sample_rate = 44100
                        self.audio_channels = 2
                        self.audio_buffer = []
                        self.audio_thread = None
                        self.audio_should_stop = False

                    def open(self) -> bool:
                        """Open webcam with OpenCV."""  # inserted
                        try:
                            self.cap = cv2.VideoCapture(self.device_index)
                            if not self.cap.isOpened():
                                raise RuntimeError(f'Failed to open webcam device {self.device_index}')
                            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                            if self.fps <= 0:
                                self.fps = 30.0
                            print(f'Webcam opened: device {self.device_index}')
                            print(f'  Resolution: {self.width}×{self.height}')
                            print(f'  FPS: {self.fps:.1f}')
                            return True
                        except Exception as e:
                            print(f'Error opening webcam: {e}')
                            return False
                        else:  # inserted
                            pass

                    def read_frame(self) -> Optional[np.ndarray]:
                        """Read next frame from webcam."""  # inserted
                        if self.cap is None:
                            return
                        ret, frame = self.cap.read()
                        if not ret:
                            return
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frame = cv2.flip(frame, 0)
                        frame = np.ascontiguousarray(frame, dtype=np.uint8)
                        return frame

                    def get_properties(self) -> Dict[str, Any]:
                        """Get webcam properties."""  # inserted
                        return {'width': self.width, 'height': self.height, 'fps': self.fps}

                    def has_audio(self) -> bool:
                        """Check if webcam has audio input."""  # inserted
                        return self.enable_audio

                    def start_audio(self) -> bool:
                        """Start capturing audio from webcam microphone."""  # inserted
                        if not self.enable_audio:
                            return False
                        try:
                            if not self.audio_initialized:
                                if not pygame.mixer.get_init():
                                    pygame.mixer.init(frequency=self.audio_sample_rate, channels=self.audio_channels)
                                self.audio_initialized = True
                            self.audio_should_stop = False
                            self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
                            self.audio_thread.start()
                            self.audio_ready = True
                            print('🔊 Webcam audio capture started')
                            return True
                        except Exception as e:
                            print(f'❌ Failed to start webcam audio: {e}')
                            self.enable_audio = False
                            self.audio_ready = False
                            return False
                        else:  # inserted
                            pass

                    def _audio_capture_loop(self):
                        """Capture audio from webcam and stream to pygame."""  # inserted
                        try:
                            def audio_callback(indata, frames, time, status):
                                """Callback for audio capture."""  # inserted
                                if self.audio_should_stop:
                                    return
                                audio_data = (indata * 32767).astype(np.int16)
                                if len(audio_data.shape) == 1:
                                    audio_data = np.column_stack((audio_data, audio_data))
                                else:  # inserted
                                    if audio_data.shape[1] == 1:
                                        audio_data = np.column_stack((audio_data, audio_data))
                                try:
                                    sound = pygame.sndarray.make_sound(audio_data)
                                    sound.play()
                                except Exception:
                                    return None
                                else:  # inserted
                                    pass
                        except Exception as e:
                            pass  # postinserted
                        else:  # inserted
                            try:
                                default_device = sd.default.device[0]
                                if default_device is None:
                                    devices = sd.query_devices()
                                    input_device = None
                                    for i, device in enumerate(devices):
                                        if device['max_input_channels'] > 0:
                                            input_device = i
                                            break
                                    if input_device is None:
                                        raise RuntimeError('No audio input device found')
                                    default_device = input_device
                            except Exception:
                                pass  # postinserted
                        else:  # inserted
                            with sd.InputStream(device=default_device, samplerate=self.audio_sample_rate, channels=min(self.audio_channels, 2), callback=audio_callback, blocksize=1024):
                                while not self.audio_should_stop:
                                    time.sleep(0.1)
                                default_device = None
                                print(f'Webcam audio capture error: {e}')
                                print('  Audio capture disabled. Webcam will work without audio.')
                                self.audio_ready = False
                                self.enable_audio = False

                    def stop_audio(self):
                        """Stop audio capture."""  # inserted
                        self.audio_should_stop = True
                        if self.audio_thread is not None and self.audio_thread.is_alive():
                            self.audio_thread.join(timeout=1.0)
                        self.audio_ready = False

                    def cleanup(self):
                        """Close webcam and clean up audio."""  # inserted
                        self.stop_audio()
                        if self.cap is not None:
                            self.cap.release()
                            self.cap = None
                        self.audio_ready = False

                class VideoUniformSource(UniformSource):
                    """\n    Provides video frames as shader uniforms and texture data.\n\n    The video texture is made available via iChannel0 to shaders.\n    Works with any FrameReader backend (video files, webcam, etc.).\n    """

                    def __init__(self, frame_reader: FrameReader, buffer_size: int=3, enable_audio: bool=True):
                        """\n        Initialize video uniform source with FrameReader backend.\n\n        Args:\n            frame_reader: FrameReader instance (VideoFileFrameReader, WebcamFrameReader, etc.)\n            buffer_size: Number of frames to buffer (3-5 recommended)\n            enable_audio: Whether to enable audio (if supported by frame reader)\n        """  # inserted
                        self.frame_reader = frame_reader
                        self.enable_audio = enable_audio and frame_reader.has_audio()
                        if not self.frame_reader.open():
                            raise RuntimeError('Failed to open frame source')
                        props = self.frame_reader.get_properties()
                        self.width = props.get('width', 0)
                        self.height = props.get('height', 0)
                        self.fps = props.get('fps', 30.0)
                        self.total_frames = props.get('total_frames', 0)
                        self.frame_count = 0
                        self.start_time = time.time()
                        self.audio_muted = False
                        self.audio_ready = False
                        self.audio_start_time = None
                        self.frame_buffer = VideoFrameBuffer(buffer_size=buffer_size)
                        self.decoder_thread = None
                        self.decoder_running = False
                        self.decoder_should_stop = False
                        self.needs_decoder_thread = isinstance(frame_reader, VideoFileFrameReader)
                        if self.needs_decoder_thread:
                            self._start_decoder_thread()
                        if self.enable_audio:
                            self.frame_reader.start_audio()
                            self.audio_ready = self.frame_reader.audio_ready
                            self.audio_start_time = time.time() if self.audio_ready else None

                    @classmethod
                    pass
                    pass
                    def from_file(cls, video_path: str, loop: bool=True, buffer_size: int=3, enable_audio: bool=True, audio_file_path: Optional[str]=None):
                        """Factory method to create VideoUniformSource from video file."""  # inserted
                        frame_reader = VideoFileFrameReader(Path(video_path), loop=loop)
                        if audio_file_path is not None and Path(audio_file_path).exists():
                            frame_reader.audio_file = audio_file_path
                            frame_reader.audio_file_owned = False
                            instance = cls(frame_reader, buffer_size=buffer_size, enable_audio=enable_audio)
                            if enable_audio:
                                frame_reader._play_audio()
                                instance.audio_ready = frame_reader.audio_ready
                                instance.audio_start_time = time.time() if instance.audio_ready else None
                            return instance
                        return cls(frame_reader, buffer_size=buffer_size, enable_audio=enable_audio)

                    @classmethod
                    def from_webcam(cls, device_index: int=0, buffer_size: int=3, enable_audio: bool=True):
                        """Factory method to create VideoUniformSource from webcam."""  # inserted
                        frame_reader = WebcamFrameReader(device_index=device_index)
                        return cls(frame_reader, buffer_size=buffer_size, enable_audio=enable_audio)

                    def _start_decoder_thread(self):
                        """Start background decoder thread (for video files with audio sync)."""  # inserted
                        self.decoder_should_stop = False
                        self.decoder_running = True
                        self.decoder_thread = threading.Thread(target=self._decoder_loop, daemon=True)
                        self.decoder_thread.start()

                    def _decoder_loop(self):
                        """Background decoder loop - syncs video frames to audio position."""  # inserted
                        if not isinstance(self.frame_reader, VideoFileFrameReader):
                            return
                        frame_time = 1.0 / max(1, self.fps)
                        last_decode_time = time.time()
                        cap = self.frame_reader.get_cap()
                        while not self.decoder_should_stop:
                            try:
                                should_throttle = False
                                if self.enable_audio and self.audio_ready:
                                    pass  # postinserted
                            except Exception as e:
                                else:  # inserted
                                    try:
                                        if pygame.mixer.music.get_busy():
                                            audio_pos_ms = pygame.mixer.music.get_pos()
                                            if self.audio_start_time and time.time() - self.audio_start_time < 0.5:
                                                should_throttle = True
                                            else:  # inserted
                                                if audio_pos_ms >= 0:
                                                    audio_pos_sec = audio_pos_ms / 1000.0
                                                    target_frame = int(audio_pos_sec * self.fps)
                                                    current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                                                    if current_frame > target_frame + 2:
                                                        time.sleep(0.005)
                                    except Exception as e:
                                                    else:  # inserted
                                                        continue
                                                    if target_frame > current_frame + 5:
                                                        self.frame_reader.set_frame_position(target_frame)
                                        else:  # inserted
                                            should_throttle = True
                            else:  # inserted
                                if should_throttle or not self.enable_audio or (not self.audio_ready):
                                    current_time = time.time()
                                    elapsed = current_time - last_decode_time
                                    if elapsed < frame_time:
                                        time.sleep(max(0.001, frame_time - elapsed))
                                    else:  # inserted
                                        continue
                                    last_decode_time = current_time
                                frame = self.frame_reader.read_frame()
                                if frame is not None:
                                    self.frame_buffer.put_frame(frame)
                                    self.frame_count += 1
                                else:  # inserted
                                    if isinstance(self.frame_reader, VideoFileFrameReader) and self.frame_reader.loop:
                                        self.frame_reader.set_frame_position(0)
                                        self.frame_count = 0
                                    else:  # inserted
                                        break
                                        self.decoder_running = False
                                if self.frame_count % 120 == 0 and self.enable_audio and self.audio_ready:
                                    audio_pos_ms = pygame.mixer.music.get_pos()
                                    if audio_pos_ms >= 0:
                                        audio_pos_sec = audio_pos_ms / 1000.0
                                        video_pos_sec = self.frame_count / self.fps
                                        drift = video_pos_sec - audio_pos_sec
                                        if abs(drift) > 0.2:
                                            print(f'   A/V drift: {drift:+.2f}s')
                                    time.sleep(0.001)
                        self.decoder_running = False
                                            should_throttle = True
                                        print(f'Decoder thread error: {e}')
                                        import traceback
                                        traceback.print_exc()
                                        return None

                    def update(self, dt: float):
                        """\n        Update video playback.\n\n        Args:\n            dt: Delta time since last update\n        """  # inserted
                        if not self.needs_decoder_thread:
                            frame = self.frame_reader.read_frame()
                            if frame is not None:
                                self.frame_buffer.put_frame(frame)
                                self.frame_count += 1

                    def get_uniforms(self) -> Dict[str, Any]:
                        """\n        Get video frame as uniforms.\n\n        Returns:\n            Dictionary with frame data and metadata\n        """  # inserted
                        uniforms = {}
                        if isinstance(self.frame_reader, VideoFileFrameReader):
                            uniforms['iVideoFrame'] = self.frame_count
                            uniforms['iVideoDuration'] = self.total_frames / max(1, self.fps)
                        return uniforms

                    def get_frame_data(self) -> Optional[np.ndarray]:
                        """\n        Get current video frame as RGB numpy array from buffer.\n\n        Returns:\n            Frame data (height, width, 3) or None if no frame available\n        """  # inserted
                        return self.frame_buffer.get_frame()

                    def toggle_audio(self):
                        """Toggle audio mute/unmute."""  # inserted
                        if not self.enable_audio or not self.audio_ready:
                            return None
                        self.audio_muted = not self.audio_muted
                        if self.audio_muted:
                            pygame.mixer.music.set_volume(0.0)
                            return self.audio_muted
                        pygame.mixer.music.set_volume(1.0)
                        return self.audio_muted

                    def is_audio_muted(self) -> bool:
                        """Check if audio is muted."""  # inserted
                        return self.audio_muted

                    def cleanup(self):
                        """Close frame source, stop decoder thread, and clean up audio."""  # inserted
                        self.decoder_should_stop = True
                        if self.decoder_thread is not None and self.decoder_thread.is_alive():
                            self.decoder_thread.join(timeout=1.0)
                        if self.enable_audio:
                            self.frame_reader.stop_audio()
                        self.frame_reader.cleanup()
                        self.frame_buffer.clear()
                        self.audio_ready = False
                        self.audio_start_time = None

                    def reset(self):
                        """Reset video to beginning (only for video files)."""  # inserted
                        if isinstance(self.frame_reader, VideoFileFrameReader):
                            self.frame_reader.set_frame_position(0)
                            self.start_time = time.time()
                            self.frame_count = 0
                            self.frame_buffer.clear()
    CV2_AVAILABLE = False
    print('Warning: opencv-python not installed. Video support disabled.')
    print('Install with: pip install opencv-python')
else:  # inserted
    pass
    PYGAME_AVAILABLE = False
    print('Warning: pygame not available - video audio disabled')
    print('Install with: pip install pygame')
else:  # inserted
    pass
    try:
        from moviepy.editor import VideoFileClip
        MOVIEPY_AVAILABLE = True
    except ImportError as e:
        MOVIEPY_AVAILABLE = False
        print('Warning: moviepy not available - video audio disabled')
        print('Install with: pip install moviepy')
    SOUNDDEVICE_AVAILABLE = False
    print('Warning: sounddevice not available - webcam audio capture disabled')
    print('Install with: pip install sounddevice')