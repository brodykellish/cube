import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

interface VideoPlayerProps {
  apiUrl: string;
  width?: number;
  height?: number;
  autoStart?: boolean;
}

interface StreamStats {
  fps: number;
  bandwidth_mbps: number;
  total_latency_ms: number;
  dropped_frames: number;
}

export default function VideoPlayer({
  apiUrl,
  width = 768,
  height = 128,
  autoStart = false
}: VideoPlayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const socketRef = useRef<Socket | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);
  const [stats, setStats] = useState<StreamStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  // FPS calculation
  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(Date.now());

  useEffect(() => {
    if (autoStart) {
      startStreaming();
    }

    return () => {
      stopStreaming();
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  const startStreaming = async () => {
    try {
      // Start streaming on backend
      const response = await fetch(`${apiUrl}/api/streaming/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_fps: 60,
          jpeg_quality: 80
        })
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || 'Failed to start streaming');
      }

      // Connect WebSocket
      connectWebSocket();
      setIsStreaming(true);
      setError(null);
    } catch (err: any) {
      setError(err.message);
      console.error('[VideoPlayer] Failed to start streaming:', err);
    }
  };

  const stopStreaming = async () => {
    try {
      // Disconnect WebSocket
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }

      // Stop streaming on backend
      await fetch(`${apiUrl}/api/streaming/stop`, {
        method: 'POST'
      });

      setIsStreaming(false);
      setIsConnected(false);
      setFps(0);
      setLatency(0);
      setStats(null);
    } catch (err) {
      console.error('[VideoPlayer] Failed to stop streaming:', err);
    }
  };

  const connectWebSocket = () => {
    // Extract host from apiUrl
    const url = new URL(apiUrl);
    const wsUrl = `${url.protocol}//${url.host}`;

    const socket = io(`${wsUrl}/stream`, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    socket.on('connect', () => {
      console.log('[VideoPlayer] WebSocket connected');
      setIsConnected(true);
      setError(null);
    });

    socket.on('disconnect', () => {
      console.log('[VideoPlayer] WebSocket disconnected');
      setIsConnected(false);
    });

    socket.on('connect_error', (err) => {
      console.error('[VideoPlayer] WebSocket connection error:', err);
      setError(`WebSocket error: ${err.message}`);
    });

    socket.on('video_frame', (data: { data: string; timestamp: number; format: string }) => {
      handleFrame(data);
    });

    socketRef.current = socket;
  };

  const handleFrame = (data: { data: string; timestamp: number; format: string }) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    try {
      // Decode base64 JPEG data
      const binaryData = atob(data.data);
      const bytes = new Uint8Array(binaryData.length);
      for (let i = 0; i < binaryData.length; i++) {
        bytes[i] = binaryData.charCodeAt(i);
      }

      const blob = new Blob([bytes], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);

      const img = new Image();
      img.onload = () => {
        // Draw frame to canvas
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);

        // Calculate latency
        const now = Date.now() / 1000;
        const frameLatency = (now - data.timestamp) * 1000;
        setLatency(Math.round(frameLatency));

        // Calculate FPS
        frameCountRef.current++;
        const elapsed = Date.now() - lastFpsUpdateRef.current;
        if (elapsed >= 1000) {
          setFps(frameCountRef.current);
          frameCountRef.current = 0;
          lastFpsUpdateRef.current = Date.now();

          // Fetch backend stats
          fetchStats();
        }
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        console.error('[VideoPlayer] Failed to decode frame');
      };
      img.src = url;
    } catch (err) {
      console.error('[VideoPlayer] Error handling frame:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/streaming/status`);
      const data = await response.json();
      if (data.success && data.streaming && data.stats) {
        setStats(data.stats);
      }
    } catch (err) {
      console.error('[VideoPlayer] Failed to fetch stats:', err);
    }
  };

  const toggleFullscreen = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (!document.fullscreenElement) {
      canvas.requestFullscreen().catch(err => {
        console.error('[VideoPlayer] Fullscreen error:', err);
      });
    } else {
      document.exitFullscreen();
    }
  };

  return (
    <div className="flex flex-col items-center space-y-4 p-4 bg-gray-800 rounded-lg">
      {/* Video Canvas */}
      <div className="relative">
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          className="border-2 border-gray-600 rounded cursor-pointer bg-black"
          onClick={toggleFullscreen}
          title="Click for fullscreen"
        />
        {!isConnected && isStreaming && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-70 text-white">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-2"></div>
              <p>Connecting...</p>
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center space-x-4">
        <button
          onClick={isStreaming ? stopStreaming : startStreaming}
          className={`px-4 py-2 rounded font-semibold ${
            isStreaming
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-green-600 hover:bg-green-700 text-white'
          }`}
        >
          {isStreaming ? 'Stop Stream' : 'Start Stream'}
        </button>

        <button
          onClick={toggleFullscreen}
          disabled={!isConnected}
          className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Fullscreen
        </button>
      </div>

      {/* Stats Display */}
      <div className="w-full grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div className="bg-gray-700 p-3 rounded">
          <div className="text-gray-400 text-xs mb-1">Client FPS</div>
          <div className="text-white font-mono text-lg">{fps}</div>
        </div>

        <div className="bg-gray-700 p-3 rounded">
          <div className="text-gray-400 text-xs mb-1">Latency</div>
          <div className="text-white font-mono text-lg">{latency} ms</div>
        </div>

        {stats && (
          <>
            <div className="bg-gray-700 p-3 rounded">
              <div className="text-gray-400 text-xs mb-1">Backend FPS</div>
              <div className="text-white font-mono text-lg">{stats.fps}</div>
            </div>

            <div className="bg-gray-700 p-3 rounded">
              <div className="text-gray-400 text-xs mb-1">Bandwidth</div>
              <div className="text-white font-mono text-lg">{stats.bandwidth_mbps.toFixed(1)} Mbps</div>
            </div>

            <div className="bg-gray-700 p-3 rounded">
              <div className="text-gray-400 text-xs mb-1">Total Latency</div>
              <div className="text-white font-mono text-lg">{stats.total_latency_ms.toFixed(0)} ms</div>
            </div>

            <div className="bg-gray-700 p-3 rounded">
              <div className="text-gray-400 text-xs mb-1">Dropped Frames</div>
              <div className="text-white font-mono text-lg">{stats.dropped_frames}</div>
            </div>
          </>
        )}
      </div>

      {/* Connection Status */}
      <div className="flex items-center space-x-2 text-sm">
        <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
        <span className="text-gray-300">
          {isConnected ? 'Connected' : isStreaming ? 'Connecting...' : 'Disconnected'}
        </span>
      </div>

      {/* Error Display */}
      {error && (
        <div className="w-full p-3 bg-red-900 border border-red-700 rounded text-red-200 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Info Text */}
      <div className="text-gray-400 text-xs text-center max-w-md">
        Target: 60 FPS @ 150-250ms latency. Click canvas for fullscreen.
        Start visualization before streaming.
      </div>
    </div>
  );
}
