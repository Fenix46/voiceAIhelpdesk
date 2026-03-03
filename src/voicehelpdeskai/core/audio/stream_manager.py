"""Advanced audio streaming manager for WebSocket connections."""

import asyncio
import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Set, Callable, Any, List
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from loguru import logger

from voicehelpdeskai.config.manager import get_config_manager
from voicehelpdeskai.core.audio.exceptions import StreamingError
from voicehelpdeskai.core.audio.processor import AudioProcessor


class StreamState(Enum):
    """Audio stream states."""
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class BackpressureStrategy(Enum):
    """Backpressure handling strategies."""
    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    BLOCK = "block"
    COMPRESS = "compress"


@dataclass
class StreamMetrics:
    """Metrics for an audio stream."""
    stream_id: str
    created_at: float = field(default_factory=time.time)
    total_chunks_sent: int = 0
    total_chunks_received: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    packet_loss_count: int = 0
    average_latency: float = 0.0
    peak_latency: float = 0.0
    connection_drops: int = 0
    last_activity: float = field(default_factory=time.time)
    backpressure_events: int = 0
    quality_degradation_events: int = 0
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def add_sent_chunk(self, byte_size: int):
        """Record a sent chunk."""
        self.total_chunks_sent += 1
        self.total_bytes_sent += byte_size
        self.update_activity()
    
    def add_received_chunk(self, byte_size: int):
        """Record a received chunk."""
        self.total_chunks_received += 1
        self.total_bytes_received += byte_size
        self.update_activity()
    
    def update_latency(self, latency: float):
        """Update latency metrics."""
        if self.average_latency == 0:
            self.average_latency = latency
        else:
            # Rolling average
            self.average_latency = 0.9 * self.average_latency + 0.1 * latency
        
        if latency > self.peak_latency:
            self.peak_latency = latency
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        uptime = time.time() - self.created_at
        return {
            "stream_id": self.stream_id,
            "uptime_seconds": uptime,
            "chunks_sent": self.total_chunks_sent,
            "chunks_received": self.total_chunks_received,
            "bytes_sent": self.total_bytes_sent,
            "bytes_received": self.total_bytes_received,
            "packet_loss_rate": self.packet_loss_count / max(self.total_chunks_sent, 1),
            "average_latency_ms": self.average_latency * 1000,
            "peak_latency_ms": self.peak_latency * 1000,
            "connection_drops": self.connection_drops,
            "backpressure_events": self.backpressure_events,
            "quality_degradation_events": self.quality_degradation_events,
            "throughput_bps": self.total_bytes_sent / max(uptime, 1),
        }


@dataclass
class StreamConfig:
    """Configuration for an audio stream."""
    stream_id: str
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    buffer_size: int = 10  # seconds
    max_latency: float = 0.5  # seconds
    backpressure_strategy: BackpressureStrategy = BackpressureStrategy.DROP_OLDEST
    enable_compression: bool = True
    quality_adaptation: bool = True
    reconnect_attempts: int = 5
    reconnect_backoff_base: float = 1.0
    reconnect_backoff_max: float = 30.0
    heartbeat_interval: float = 30.0
    timeout: float = 60.0


class AudioChunk:
    """Audio chunk with metadata."""
    
    def __init__(self, 
                 data: np.ndarray,
                 timestamp: Optional[float] = None,
                 chunk_id: Optional[str] = None,
                 sample_rate: int = 16000):
        """Initialize audio chunk.
        
        Args:
            data: Audio data array
            timestamp: Timestamp when chunk was created
            chunk_id: Unique chunk identifier
            sample_rate: Audio sample rate
        """
        self.data = data
        self.timestamp = timestamp or time.time()
        self.chunk_id = chunk_id or str(uuid.uuid4())
        self.sample_rate = sample_rate
        self.byte_size = data.nbytes if hasattr(data, 'nbytes') else len(data) * 4
        self.sequence_number = 0
        
    def to_bytes(self) -> bytes:
        """Convert chunk to bytes."""
        return self.data.tobytes()
    
    def to_json(self) -> str:
        """Convert chunk metadata to JSON."""
        return json.dumps({
            "chunk_id": self.chunk_id,
            "timestamp": self.timestamp,
            "sample_rate": self.sample_rate,
            "byte_size": self.byte_size,
            "sequence_number": self.sequence_number,
            "data_shape": list(self.data.shape) if hasattr(self.data, 'shape') else None,
        })
    
    @classmethod
    def from_bytes(cls, data: bytes, **kwargs) -> 'AudioChunk':
        """Create chunk from bytes."""
        audio_array = np.frombuffer(data, dtype=np.float32)
        return cls(audio_array, **kwargs)


class StreamConnection:
    """Manages a single WebSocket audio stream connection."""
    
    def __init__(self, 
                 websocket,
                 config: StreamConfig,
                 stream_manager: 'AudioStreamManager'):
        """Initialize stream connection.
        
        Args:
            websocket: WebSocket connection
            config: Stream configuration
            stream_manager: Parent stream manager
        """
        self.websocket = websocket
        self.config = config
        self.stream_manager = stream_manager
        self.state = StreamState.IDLE
        self.metrics = StreamMetrics(config.stream_id)
        
        # Buffers
        self.input_buffer = deque(maxlen=self._calculate_buffer_size())
        self.output_buffer = deque(maxlen=self._calculate_buffer_size())
        
        # Streaming state
        self.is_active = False
        self.last_heartbeat = time.time()
        self.sequence_number = 0
        self.expected_sequence = 0
        
        # Quality adaptation
        self.current_quality = 1.0
        self.latency_history = deque(maxlen=10)
        
        # Reconnection
        self.reconnect_attempts = 0
        self.last_reconnect = 0
        
        logger.info(f"Stream connection created: {config.stream_id}")
    
    def _calculate_buffer_size(self) -> int:
        """Calculate buffer size based on configuration."""
        chunks_per_second = self.config.sample_rate // self.config.chunk_size
        return int(chunks_per_second * self.config.buffer_size)
    
    async def start_streaming(self):
        """Start audio streaming."""
        try:
            self.state = StreamState.CONNECTING
            self.is_active = True
            
            # Send initial configuration
            await self._send_config()
            
            self.state = StreamState.STREAMING
            logger.info(f"Stream started: {self.config.stream_id}")
            
        except Exception as e:
            self.state = StreamState.ERROR
            raise StreamingError(f"Failed to start stream: {e}")
    
    async def stop_streaming(self):
        """Stop audio streaming."""
        try:
            self.is_active = False
            self.state = StreamState.DISCONNECTED
            
            # Send stop signal
            await self._send_control_message("stop")
            
            logger.info(f"Stream stopped: {self.config.stream_id}")
            
        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
    
    async def send_audio_chunk(self, chunk: AudioChunk) -> bool:
        """Send audio chunk over WebSocket.
        
        Args:
            chunk: Audio chunk to send
            
        Returns:
            True if sent successfully
        """
        if not self.is_active or self.state != StreamState.STREAMING:
            return False
        
        try:
            start_time = time.time()
            
            # Handle backpressure
            if len(self.output_buffer) >= self.output_buffer.maxlen:
                await self._handle_backpressure()
            
            # Apply quality adaptation
            if self.config.quality_adaptation:
                chunk = await self._adapt_quality(chunk)
            
            # Set sequence number
            chunk.sequence_number = self.sequence_number
            self.sequence_number += 1
            
            # Send chunk
            message = {
                "type": "audio_chunk",
                "metadata": json.loads(chunk.to_json()),
                "data": chunk.to_bytes().hex()  # Hex encode for JSON transmission
            }
            
            await self.websocket.send_text(json.dumps(message))
            
            # Update metrics
            latency = time.time() - start_time
            self.metrics.add_sent_chunk(chunk.byte_size)
            self.metrics.update_latency(latency)
            self.latency_history.append(latency)
            
            # Store in output buffer for potential retransmission
            self.output_buffer.append(chunk)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send audio chunk: {e}")
            self.metrics.packet_loss_count += 1
            return False
    
    async def receive_audio_chunk(self, message: Dict[str, Any]) -> Optional[AudioChunk]:
        """Receive and process audio chunk from WebSocket.
        
        Args:
            message: Received WebSocket message
            
        Returns:
            Processed audio chunk or None
        """
        try:
            metadata = message.get("metadata", {})
            data_hex = message.get("data", "")
            
            # Decode data
            data_bytes = bytes.fromhex(data_hex)
            audio_data = np.frombuffer(data_bytes, dtype=np.float32)
            
            # Create chunk
            chunk = AudioChunk(
                data=audio_data,
                chunk_id=metadata.get("chunk_id"),
                timestamp=metadata.get("timestamp", time.time()),
                sample_rate=metadata.get("sample_rate", self.config.sample_rate)
            )
            
            chunk.sequence_number = metadata.get("sequence_number", 0)
            
            # Check sequence number for packet loss
            if chunk.sequence_number != self.expected_sequence:
                self.metrics.packet_loss_count += 1
                logger.warning(f"Packet loss detected: expected {self.expected_sequence}, got {chunk.sequence_number}")
            
            self.expected_sequence = chunk.sequence_number + 1
            
            # Update metrics
            self.metrics.add_received_chunk(chunk.byte_size)
            
            # Store in input buffer
            if len(self.input_buffer) >= self.input_buffer.maxlen:
                # Buffer full, apply backpressure strategy
                await self._handle_input_backpressure()
            
            self.input_buffer.append(chunk)
            
            return chunk
            
        except Exception as e:
            logger.error(f"Failed to receive audio chunk: {e}")
            return None
    
    async def _handle_backpressure(self):
        """Handle output buffer backpressure."""
        self.metrics.backpressure_events += 1
        
        strategy = self.config.backpressure_strategy
        
        if strategy == BackpressureStrategy.DROP_OLDEST:
            # Remove oldest chunks
            while len(self.output_buffer) >= self.output_buffer.maxlen * 0.8:
                self.output_buffer.popleft()
                
        elif strategy == BackpressureStrategy.DROP_NEWEST:
            # Don't add new chunks when buffer is full
            pass
            
        elif strategy == BackpressureStrategy.COMPRESS:
            # Reduce quality temporarily
            self.current_quality *= 0.8
            self.metrics.quality_degradation_events += 1
            
        elif strategy == BackpressureStrategy.BLOCK:
            # Wait for buffer to clear
            while len(self.output_buffer) >= self.output_buffer.maxlen * 0.5:
                await asyncio.sleep(0.01)
    
    async def _handle_input_backpressure(self):
        """Handle input buffer backpressure."""
        # Simply drop oldest chunks
        while len(self.input_buffer) >= self.input_buffer.maxlen * 0.8:
            self.input_buffer.popleft()
    
    async def _adapt_quality(self, chunk: AudioChunk) -> AudioChunk:
        """Adapt audio quality based on network conditions.
        
        Args:
            chunk: Input audio chunk
            
        Returns:
            Quality-adapted audio chunk
        """
        if not self.latency_history:
            return chunk
        
        # Calculate average latency
        avg_latency = sum(self.latency_history) / len(self.latency_history)
        
        # Adjust quality based on latency
        if avg_latency > self.config.max_latency:
            # High latency - reduce quality
            self.current_quality = max(0.3, self.current_quality * 0.9)
            self.metrics.quality_degradation_events += 1
        elif avg_latency < self.config.max_latency * 0.5:
            # Low latency - can increase quality
            self.current_quality = min(1.0, self.current_quality * 1.1)
        
        # Apply quality scaling (simple amplitude scaling)
        if self.current_quality < 1.0:
            scaled_data = chunk.data * self.current_quality
            return AudioChunk(
                data=scaled_data,
                timestamp=chunk.timestamp,
                chunk_id=chunk.chunk_id,
                sample_rate=chunk.sample_rate
            )
        
        return chunk
    
    async def _send_config(self):
        """Send stream configuration to client."""
        config_message = {
            "type": "stream_config",
            "config": {
                "stream_id": self.config.stream_id,
                "sample_rate": self.config.sample_rate,
                "channels": self.config.channels,
                "chunk_size": self.config.chunk_size,
            }
        }
        
        await self.websocket.send_text(json.dumps(config_message))
    
    async def _send_control_message(self, command: str):
        """Send control message to client.
        
        Args:
            command: Control command
        """
        control_message = {
            "type": "control",
            "command": command,
            "stream_id": self.config.stream_id
        }
        
        await self.websocket.send_text(json.dumps(control_message))
    
    async def send_heartbeat(self):
        """Send heartbeat to keep connection alive."""
        try:
            heartbeat_message = {
                "type": "heartbeat",
                "timestamp": time.time(),
                "stream_id": self.config.stream_id
            }
            
            await self.websocket.send_text(json.dumps(heartbeat_message))
            self.last_heartbeat = time.time()
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    def is_timeout(self) -> bool:
        """Check if connection has timed out."""
        return time.time() - self.last_heartbeat > self.config.timeout
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get stream metrics."""
        return self.metrics.get_summary()


class AudioStreamManager:
    """Manages multiple concurrent audio streams over WebSocket."""
    
    def __init__(self, config_manager=None):
        """Initialize audio stream manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or get_config_manager()
        self.settings = self.config_manager.get_settings()
        
        # Active connections
        self.connections: Dict[str, StreamConnection] = {}
        self.websockets: Dict[str, Any] = {}  # WebSocket instances
        
        # Audio processor
        self.audio_processor = AudioProcessor(config_manager)
        
        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()
        self.is_running = False
        
        # Thread pool for CPU-intensive tasks
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Global metrics
        self.total_connections = 0
        self.active_connections = 0
        self.total_bytes_transferred = 0
        
        logger.info("AudioStreamManager initialized")
    
    async def start(self):
        """Start the stream manager."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start background tasks
        task1 = asyncio.create_task(self._heartbeat_loop())
        task2 = asyncio.create_task(self._cleanup_loop())
        task3 = asyncio.create_task(self._metrics_loop())
        
        self.background_tasks.update([task1, task2, task3])
        
        logger.info("AudioStreamManager started")
    
    async def stop(self):
        """Stop the stream manager."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop all connections
        for stream_id in list(self.connections.keys()):
            await self.disconnect_stream(stream_id)
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Cleanup audio processor
        self.audio_processor.cleanup()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        logger.info("AudioStreamManager stopped")
    
    async def create_stream(self, 
                           websocket,
                           stream_config: Optional[StreamConfig] = None) -> str:
        """Create a new audio stream.
        
        Args:
            websocket: WebSocket connection
            stream_config: Stream configuration (optional)
            
        Returns:
            Stream ID
        """
        stream_id = str(uuid.uuid4())
        
        # Use default config if not provided
        if stream_config is None:
            stream_config = StreamConfig(
                stream_id=stream_id,
                sample_rate=self.settings.audio.sample_rate,
                channels=self.settings.audio.channels,
                chunk_size=self.settings.audio.chunk_size,
            )
        else:
            stream_config.stream_id = stream_id
        
        try:
            # Create connection
            connection = StreamConnection(websocket, stream_config, self)
            
            # Store connection
            self.connections[stream_id] = connection
            self.websockets[stream_id] = websocket
            
            # Update metrics
            self.total_connections += 1
            self.active_connections += 1
            
            logger.info(f"Stream created: {stream_id}")
            return stream_id
            
        except Exception as e:
            raise StreamingError(f"Failed to create stream: {e}")
    
    async def connect_stream(self, stream_id: str) -> bool:
        """Connect and start streaming for a stream.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            True if connected successfully
        """
        connection = self.connections.get(stream_id)
        if not connection:
            logger.error(f"Stream not found: {stream_id}")
            return False
        
        try:
            await connection.start_streaming()
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect stream {stream_id}: {e}")
            return False
    
    async def disconnect_stream(self, stream_id: str) -> bool:
        """Disconnect and remove a stream.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            True if disconnected successfully
        """
        connection = self.connections.get(stream_id)
        if not connection:
            return True  # Already disconnected
        
        try:
            await connection.stop_streaming()
            
            # Remove from collections
            del self.connections[stream_id]
            if stream_id in self.websockets:
                del self.websockets[stream_id]
            
            # Update metrics
            self.active_connections = max(0, self.active_connections - 1)
            
            logger.info(f"Stream disconnected: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting stream {stream_id}: {e}")
            return False
    
    async def send_audio_to_stream(self, 
                                  stream_id: str,
                                  audio_data: np.ndarray) -> bool:
        """Send audio data to a specific stream.
        
        Args:
            stream_id: Stream identifier
            audio_data: Audio data to send
            
        Returns:
            True if sent successfully
        """
        connection = self.connections.get(stream_id)
        if not connection:
            logger.error(f"Stream not found: {stream_id}")
            return False
        
        try:
            # Create audio chunk
            chunk = AudioChunk(audio_data, sample_rate=connection.config.sample_rate)
            
            # Send chunk
            return await connection.send_audio_chunk(chunk)
            
        except Exception as e:
            logger.error(f"Failed to send audio to stream {stream_id}: {e}")
            return False
    
    async def broadcast_audio(self, audio_data: np.ndarray) -> int:
        """Broadcast audio data to all active streams.
        
        Args:
            audio_data: Audio data to broadcast
            
        Returns:
            Number of streams that received the data
        """
        if not self.connections:
            return 0
        
        success_count = 0
        
        # Send to all active streams
        for stream_id in list(self.connections.keys()):
            if await self.send_audio_to_stream(stream_id, audio_data):
                success_count += 1
        
        return success_count
    
    async def handle_websocket_message(self, 
                                     stream_id: str,
                                     message: Dict[str, Any]) -> bool:
        """Handle incoming WebSocket message.
        
        Args:
            stream_id: Stream identifier
            message: Received message
            
        Returns:
            True if handled successfully
        """
        connection = self.connections.get(stream_id)
        if not connection:
            logger.error(f"Stream not found: {stream_id}")
            return False
        
        try:
            message_type = message.get("type", "")
            
            if message_type == "audio_chunk":
                chunk = await connection.receive_audio_chunk(message)
                if chunk:
                    # Process received audio chunk
                    await self._process_received_audio(stream_id, chunk)
                
            elif message_type == "control":
                await self._handle_control_message(stream_id, message)
                
            elif message_type == "heartbeat":
                connection.last_heartbeat = time.time()
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            return False
    
    async def _process_received_audio(self, stream_id: str, chunk: AudioChunk):
        """Process received audio chunk.
        
        Args:
            stream_id: Stream identifier
            chunk: Received audio chunk
        """
        # Process audio in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        def process_chunk():
            return self.audio_processor.process_audio_chunk(chunk.data)
        
        try:
            processed_data = await loop.run_in_executor(self.executor, process_chunk)
            
            # Update chunk with processed data
            chunk.data = processed_data
            
            # Store processed chunk for further processing
            # This could trigger voice activity detection, transcription, etc.
            
        except Exception as e:
            logger.error(f"Error processing received audio: {e}")
    
    async def _handle_control_message(self, stream_id: str, message: Dict[str, Any]):
        """Handle control message.
        
        Args:
            stream_id: Stream identifier
            message: Control message
        """
        command = message.get("command", "")
        
        if command == "pause":
            await self._pause_stream(stream_id)
        elif command == "resume":
            await self._resume_stream(stream_id)
        elif command == "stop":
            await self.disconnect_stream(stream_id)
        else:
            logger.warning(f"Unknown control command: {command}")
    
    async def _pause_stream(self, stream_id: str):
        """Pause a stream."""
        connection = self.connections.get(stream_id)
        if connection:
            connection.state = StreamState.PAUSED
            logger.info(f"Stream paused: {stream_id}")
    
    async def _resume_stream(self, stream_id: str):
        """Resume a paused stream."""
        connection = self.connections.get(stream_id)
        if connection and connection.state == StreamState.PAUSED:
            connection.state = StreamState.STREAMING
            logger.info(f"Stream resumed: {stream_id}")
    
    async def _heartbeat_loop(self):
        """Background loop for sending heartbeats."""
        while self.is_running:
            try:
                for connection in list(self.connections.values()):
                    if connection.is_active:
                        await connection.send_heartbeat()
                
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_loop(self):
        """Background loop for cleaning up inactive connections."""
        while self.is_running:
            try:
                current_time = time.time()
                streams_to_remove = []
                
                for stream_id, connection in self.connections.items():
                    # Check for timeout
                    if connection.is_timeout():
                        streams_to_remove.append(stream_id)
                        connection.metrics.connection_drops += 1
                
                # Remove timed out streams
                for stream_id in streams_to_remove:
                    logger.info(f"Removing timed out stream: {stream_id}")
                    await self.disconnect_stream(stream_id)
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(10)
    
    async def _metrics_loop(self):
        """Background loop for collecting metrics."""
        while self.is_running:
            try:
                # Update global metrics
                total_bytes = sum(
                    conn.metrics.total_bytes_sent + conn.metrics.total_bytes_received
                    for conn in self.connections.values()
                )
                self.total_bytes_transferred = total_bytes
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
                await asyncio.sleep(10)
    
    def get_stream_metrics(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific stream.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            Stream metrics or None
        """
        connection = self.connections.get(stream_id)
        return connection.get_metrics() if connection else None
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global stream manager metrics.
        
        Returns:
            Global metrics
        """
        return {
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "total_bytes_transferred": self.total_bytes_transferred,
            "average_latency": self._calculate_average_latency(),
            "total_packet_loss": self._calculate_total_packet_loss(),
            "active_streams": list(self.connections.keys()),
        }
    
    def _calculate_average_latency(self) -> float:
        """Calculate average latency across all streams."""
        if not self.connections:
            return 0.0
        
        latencies = [conn.metrics.average_latency for conn in self.connections.values()]
        return sum(latencies) / len(latencies)
    
    def _calculate_total_packet_loss(self) -> int:
        """Calculate total packet loss across all streams."""
        return sum(conn.metrics.packet_loss_count for conn in self.connections.values())
    
    def __del__(self):
        """Destructor."""
        try:
            if self.is_running:
                # Can't use await in destructor, so just cleanup synchronously
                self.audio_processor.cleanup()
        except:
            pass