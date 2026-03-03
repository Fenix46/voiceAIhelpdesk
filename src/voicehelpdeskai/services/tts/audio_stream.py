"""Advanced Audio Response Streaming with buffer management and format conversion."""

import asyncio
import io
import json
import struct
import time
import wave
import zlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, AsyncGenerator, Union, Any, Callable
from datetime import datetime
import numpy as np

from loguru import logger

try:
    import librosa
    import soundfile as sf
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    logger.warning("Audio processing libraries not available")

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("PyAudio not available - no direct audio playback")

from voicehelpdeskai.config.manager import get_config_manager


class StreamingFormat(Enum):
    """Streaming audio formats."""
    RAW_PCM = "raw_pcm"
    WAV_CHUNKS = "wav_chunks"  
    MP3_CHUNKS = "mp3_chunks"
    OPUS_CHUNKS = "opus_chunks"
    WEBM_CHUNKS = "webm_chunks"


class CompressionLevel(Enum):
    """Audio compression levels for bandwidth optimization."""
    NONE = "none"
    LOW = "low"      # Minimal compression
    MEDIUM = "medium" # Balanced quality/size
    HIGH = "high"    # Maximum compression
    ADAPTIVE = "adaptive"  # Adjust based on connection


class BufferStrategy(Enum):
    """Buffer management strategies."""
    FIXED_SIZE = "fixed_size"       # Fixed buffer size
    ADAPTIVE = "adaptive"           # Adapt to network conditions  
    LATENCY_OPTIMIZED = "latency_optimized"  # Minimize latency
    QUALITY_OPTIMIZED = "quality_optimized"  # Maximize quality


@dataclass
class StreamingConfig:
    """Configuration for audio streaming."""
    format: StreamingFormat = StreamingFormat.WAV_CHUNKS
    sample_rate: int = 22050
    channels: int = 1
    bit_depth: int = 16
    chunk_size: int = 1024  # Samples per chunk
    buffer_size: int = 8192  # Buffer size in bytes
    buffer_strategy: BufferStrategy = BufferStrategy.ADAPTIVE
    compression_level: CompressionLevel = CompressionLevel.MEDIUM
    enable_compression: bool = True
    enable_silence_detection: bool = True
    silence_threshold: float = 0.01
    max_silence_duration: float = 2.0  # Seconds
    playback_speed: float = 1.0
    volume: float = 1.0


@dataclass
class StreamChunk:
    """Audio stream chunk."""
    data: bytes
    sequence_number: int
    timestamp: float
    duration: float
    sample_rate: int
    channels: int
    format: StreamingFormat
    is_final: bool = False
    compressed: bool = False
    compression_ratio: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamStats:
    """Streaming statistics."""
    total_chunks: int = 0
    total_bytes: int = 0
    compressed_bytes: int = 0
    compression_ratio: float = 1.0
    avg_chunk_duration: float = 0.0
    buffer_underruns: int = 0
    buffer_overruns: int = 0
    silence_chunks_skipped: int = 0
    processing_latency: float = 0.0
    network_latency: float = 0.0


class AudioBuffer:
    """Thread-safe audio buffer with adaptive management."""
    
    def __init__(self, 
                 max_size: int = 16384,
                 strategy: BufferStrategy = BufferStrategy.ADAPTIVE):
        self.max_size = max_size
        self.strategy = strategy
        self.buffer = io.BytesIO()
        self.lock = asyncio.Lock()
        self.underrun_count = 0
        self.overrun_count = 0
        self._adaptive_size = max_size
        
    async def write(self, data: bytes) -> bool:
        """Write data to buffer.
        
        Args:
            data: Audio data to write
            
        Returns:
            True if data was written successfully
        """
        async with self.lock:
            current_size = self.buffer.tell()
            
            if current_size + len(data) > self._adaptive_size:
                if self.strategy == BufferStrategy.ADAPTIVE:
                    # Increase buffer size on overrun
                    self._adaptive_size = min(self._adaptive_size * 1.5, self.max_size * 2)
                    logger.debug(f"Buffer size adapted to {self._adaptive_size}")
                else:
                    # Buffer overrun
                    self.overrun_count += 1
                    return False
            
            self.buffer.write(data)
            return True
    
    async def read(self, size: int) -> bytes:
        """Read data from buffer.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Audio data bytes
        """
        async with self.lock:
            if self.buffer.tell() < size:
                self.underrun_count += 1
                # Return available data
                self.buffer.seek(0)
                data = self.buffer.read()
                self.buffer.seek(0)
                self.buffer.truncate(0)
                return data
            
            # Read requested amount
            self.buffer.seek(0)
            data = self.buffer.read(size)
            
            # Shift remaining data
            remaining = self.buffer.read()
            self.buffer.seek(0)
            self.buffer.truncate(0)
            self.buffer.write(remaining)
            
            return data
    
    async def size(self) -> int:
        """Get current buffer size."""
        async with self.lock:
            return self.buffer.tell()
    
    async def clear(self) -> None:
        """Clear buffer."""
        async with self.lock:
            self.buffer.seek(0)
            self.buffer.truncate(0)


class AudioResponseStream:
    """Advanced audio response streaming with adaptive buffer management."""
    
    def __init__(self,
                 config: Optional[StreamingConfig] = None,
                 enable_real_time: bool = True,
                 enable_adaptive_quality: bool = True):
        """Initialize audio response stream.
        
        Args:
            config: Streaming configuration
            enable_real_time: Enable real-time streaming optimizations
            enable_adaptive_quality: Enable adaptive quality based on conditions
        """
        self.config = config or StreamingConfig()
        self.enable_real_time = enable_real_time
        self.enable_adaptive_quality = enable_adaptive_quality
        
        # Buffers
        self.input_buffer = AudioBuffer(
            max_size=self.config.buffer_size * 4,
            strategy=self.config.buffer_strategy
        )
        self.output_buffer = AudioBuffer(
            max_size=self.config.buffer_size * 2,
            strategy=self.config.buffer_strategy
        )
        
        # State
        self.is_streaming = False
        self.sequence_number = 0
        self.start_time = 0.0
        
        # Statistics
        self.stats = StreamStats()
        
        # Processing components
        self.silence_detector = SilenceDetector(
            threshold=self.config.silence_threshold,
            max_duration=self.config.max_silence_duration
        ) if self.config.enable_silence_detection else None
        
        self.audio_compressor = AudioCompressor(
            level=self.config.compression_level
        ) if self.config.enable_compression else None
        
        logger.info("AudioResponseStream initialized")
    
    async def start_stream(self, audio_data: bytes) -> None:
        """Start streaming audio data.
        
        Args:
            audio_data: Complete audio data to stream
        """
        self.is_streaming = True
        self.start_time = time.time()
        self.sequence_number = 0
        
        # Load audio data into input buffer
        await self.input_buffer.write(audio_data)
        
        logger.info(f"Started streaming {len(audio_data)} bytes of audio")
    
    async def stream_chunks(self) -> AsyncGenerator[StreamChunk, None]:
        """Generate stream chunks from buffered audio.
        
        Yields:
            StreamChunk objects with audio data
        """
        if not self.is_streaming:
            raise RuntimeError("Stream not started")
        
        try:
            chunk_size_bytes = self.config.chunk_size * (self.config.bit_depth // 8) * self.config.channels
            
            while self.is_streaming:
                # Read chunk from input buffer
                chunk_data = await self.input_buffer.read(chunk_size_bytes)
                
                if not chunk_data:
                    # End of stream
                    yield self._create_final_chunk()
                    break
                
                # Process chunk
                processed_chunk = await self._process_chunk(chunk_data)
                
                if processed_chunk:
                    yield processed_chunk
                
                # Adaptive streaming delay
                await self._adaptive_delay()
                
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise
        finally:
            self.is_streaming = False
    
    async def stream_real_time(self, 
                             audio_generator: AsyncGenerator[bytes, None]) -> AsyncGenerator[StreamChunk, None]:
        """Stream audio in real-time from generator.
        
        Args:
            audio_generator: Async generator yielding audio data
            
        Yields:
            StreamChunk objects with real-time audio
        """
        self.is_streaming = True
        self.start_time = time.time()
        self.sequence_number = 0
        
        try:
            async for audio_data in audio_generator:
                if not audio_data:
                    continue
                
                # Process incoming audio immediately
                processed_chunk = await self._process_chunk(audio_data)
                
                if processed_chunk:
                    yield processed_chunk
                
                # Minimal delay for real-time streaming
                if self.enable_real_time:
                    await asyncio.sleep(0.001)  # 1ms
                
        except Exception as e:
            logger.error(f"Real-time streaming error: {e}")
            raise
        finally:
            # Send final chunk
            yield self._create_final_chunk()
            self.is_streaming = False
    
    async def _process_chunk(self, chunk_data: bytes) -> Optional[StreamChunk]:
        """Process a single audio chunk.
        
        Args:
            chunk_data: Raw audio data
            
        Returns:
            Processed StreamChunk or None if chunk should be skipped
        """
        start_time = time.time()
        
        try:
            # Apply playback speed modification
            if self.config.playback_speed != 1.0 and AUDIO_PROCESSING_AVAILABLE:
                chunk_data = await self._adjust_playback_speed(chunk_data)
            
            # Apply volume adjustment
            if self.config.volume != 1.0:
                chunk_data = await self._adjust_volume(chunk_data)
            
            # Silence detection
            if self.silence_detector:
                if await self.silence_detector.is_silence(chunk_data, self.config.sample_rate):
                    self.stats.silence_chunks_skipped += 1
                    return None  # Skip silent chunks
            
            # Compression
            original_size = len(chunk_data)
            compressed = False
            compression_ratio = 1.0
            
            if self.audio_compressor:
                chunk_data = await self.audio_compressor.compress(
                    chunk_data, self.config.sample_rate, self.config.channels
                )
                compressed = True
                compression_ratio = original_size / len(chunk_data) if chunk_data else 1.0
            
            # Format conversion
            chunk_data = await self._convert_chunk_format(chunk_data)
            
            # Calculate duration
            duration = (original_size / (self.config.sample_rate * self.config.channels * (self.config.bit_depth // 8)))
            
            # Create chunk
            chunk = StreamChunk(
                data=chunk_data,
                sequence_number=self.sequence_number,
                timestamp=time.time() - self.start_time,
                duration=duration,
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                format=self.config.format,
                compressed=compressed,
                compression_ratio=compression_ratio,
                metadata={
                    'original_size': original_size,
                    'processed_size': len(chunk_data),
                    'processing_time': time.time() - start_time
                }
            )
            
            # Update statistics
            self._update_chunk_stats(chunk)
            
            self.sequence_number += 1
            return chunk
            
        except Exception as e:
            logger.error(f"Chunk processing failed: {e}")
            return None
    
    async def _adjust_playback_speed(self, audio_data: bytes) -> bytes:
        """Adjust playback speed of audio chunk.
        
        Args:
            audio_data: Audio data bytes
            
        Returns:
            Speed-adjusted audio data
        """
        if not AUDIO_PROCESSING_AVAILABLE:
            return audio_data
        
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
            
            # Apply time stretching
            stretched = librosa.effects.time_stretch(audio_array, rate=self.config.playback_speed)
            
            # Convert back to bytes
            return (stretched * 32767).astype(np.int16).tobytes()
            
        except Exception as e:
            logger.error(f"Playback speed adjustment failed: {e}")
            return audio_data
    
    async def _adjust_volume(self, audio_data: bytes) -> bytes:
        """Adjust volume of audio chunk.
        
        Args:
            audio_data: Audio data bytes
            
        Returns:
            Volume-adjusted audio data
        """
        try:
            # Convert to numpy array for processing
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # Apply volume scaling
            audio_array *= self.config.volume
            
            # Prevent clipping
            audio_array = np.clip(audio_array, -32767, 32767)
            
            # Convert back to bytes
            return audio_array.astype(np.int16).tobytes()
            
        except Exception as e:
            logger.error(f"Volume adjustment failed: {e}")
            return audio_data
    
    async def _convert_chunk_format(self, chunk_data: bytes) -> bytes:
        """Convert chunk to target streaming format.
        
        Args:
            chunk_data: Raw PCM audio data
            
        Returns:
            Format-converted chunk data
        """
        if self.config.format == StreamingFormat.RAW_PCM:
            return chunk_data
        
        elif self.config.format == StreamingFormat.WAV_CHUNKS:
            # Wrap in WAV header
            return self._create_wav_chunk(chunk_data)
        
        # For other formats, return raw data (would need specific encoders)
        return chunk_data
    
    def _create_wav_chunk(self, pcm_data: bytes) -> bytes:
        """Create WAV-formatted chunk.
        
        Args:
            pcm_data: PCM audio data
            
        Returns:
            WAV-formatted chunk
        """
        # Create minimal WAV header for chunk
        wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            36 + len(pcm_data),  # File size
            b'WAVE',
            b'fmt ',
            16,  # PCM format size
            1,   # PCM format
            self.config.channels,
            self.config.sample_rate,
            self.config.sample_rate * self.config.channels * (self.config.bit_depth // 8),
            self.config.channels * (self.config.bit_depth // 8),
            self.config.bit_depth,
            b'data',
            len(pcm_data)
        )
        
        return wav_header + pcm_data
    
    def _create_final_chunk(self) -> StreamChunk:
        """Create final chunk marker."""
        return StreamChunk(
            data=b'',
            sequence_number=self.sequence_number,
            timestamp=time.time() - self.start_time,
            duration=0.0,
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.format,
            is_final=True,
            metadata={'stream_end': True}
        )
    
    async def _adaptive_delay(self) -> None:
        """Calculate and apply adaptive delay for smooth streaming."""
        if not self.enable_real_time:
            return
        
        # Calculate chunk duration
        chunk_duration = (self.config.chunk_size / self.config.sample_rate)
        
        # Adaptive delay based on buffer strategy
        if self.config.buffer_strategy == BufferStrategy.LATENCY_OPTIMIZED:
            delay = chunk_duration * 0.8  # Faster streaming
        elif self.config.buffer_strategy == BufferStrategy.QUALITY_OPTIMIZED:
            delay = chunk_duration * 1.2  # Slower for better quality
        else:
            delay = chunk_duration  # Real-time
        
        await asyncio.sleep(delay)
    
    def _update_chunk_stats(self, chunk: StreamChunk) -> None:
        """Update streaming statistics."""
        self.stats.total_chunks += 1
        self.stats.total_bytes += len(chunk.data)
        
        if chunk.compressed:
            original_size = chunk.metadata.get('original_size', len(chunk.data))
            self.stats.compressed_bytes += len(chunk.data)
            self.stats.compression_ratio = self.stats.total_bytes / self.stats.compressed_bytes if self.stats.compressed_bytes > 0 else 1.0
        
        # Update average chunk duration
        self.stats.avg_chunk_duration = (
            (self.stats.avg_chunk_duration * (self.stats.total_chunks - 1) + chunk.duration) / 
            self.stats.total_chunks
        )
        
        # Update processing latency
        processing_time = chunk.metadata.get('processing_time', 0.0)
        self.stats.processing_latency = (
            (self.stats.processing_latency * (self.stats.total_chunks - 1) + processing_time) /
            self.stats.total_chunks
        )
    
    async def stop_stream(self) -> None:
        """Stop the audio stream."""
        self.is_streaming = False
        await self.input_buffer.clear()
        await self.output_buffer.clear()
        logger.info("Audio stream stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get streaming statistics."""
        stats_dict = {
            'total_chunks': self.stats.total_chunks,
            'total_bytes': self.stats.total_bytes,
            'compressed_bytes': self.stats.compressed_bytes,
            'compression_ratio': self.stats.compression_ratio,
            'avg_chunk_duration': self.stats.avg_chunk_duration,
            'buffer_underruns': self.input_buffer.underrun_count + self.output_buffer.underrun_count,
            'buffer_overruns': self.input_buffer.overrun_count + self.output_buffer.overrun_count,
            'silence_chunks_skipped': self.stats.silence_chunks_skipped,
            'processing_latency': self.stats.processing_latency,
            'is_streaming': self.is_streaming,
            'sequence_number': self.sequence_number,
        }
        
        if self.stats.total_chunks > 0:
            stats_dict['avg_chunk_size'] = self.stats.total_bytes / self.stats.total_chunks
            stats_dict['compression_efficiency'] = (1 - (self.stats.compressed_bytes / self.stats.total_bytes)) * 100 if self.stats.total_bytes > 0 else 0
        
        return stats_dict


class SilenceDetector:
    """Detect silence in audio for streaming optimization."""
    
    def __init__(self, threshold: float = 0.01, max_duration: float = 2.0):
        self.threshold = threshold
        self.max_duration = max_duration
        self.silence_start = None
    
    async def is_silence(self, audio_data: bytes, sample_rate: int) -> bool:
        """Check if audio chunk contains silence.
        
        Args:
            audio_data: Audio data bytes
            sample_rate: Audio sample rate
            
        Returns:
            True if chunk is considered silence
        """
        try:
            # Convert to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
            
            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_array ** 2))
            
            is_silent = rms < self.threshold
            
            # Track silence duration
            current_time = time.time()
            if is_silent:
                if self.silence_start is None:
                    self.silence_start = current_time
                elif current_time - self.silence_start > self.max_duration:
                    # Too much silence, don't skip
                    return False
            else:
                self.silence_start = None
            
            return is_silent
            
        except Exception as e:
            logger.error(f"Silence detection failed: {e}")
            return False


class AudioCompressor:
    """Audio compression for bandwidth optimization."""
    
    def __init__(self, level: CompressionLevel = CompressionLevel.MEDIUM):
        self.level = level
        self.compression_ratios = {
            CompressionLevel.NONE: 1.0,
            CompressionLevel.LOW: 0.8,
            CompressionLevel.MEDIUM: 0.6,
            CompressionLevel.HIGH: 0.4,
            CompressionLevel.ADAPTIVE: 0.6  # Default for adaptive
        }
    
    async def compress(self, 
                     audio_data: bytes, 
                     sample_rate: int, 
                     channels: int) -> bytes:
        """Compress audio data.
        
        Args:
            audio_data: Raw audio data
            sample_rate: Audio sample rate  
            channels: Number of channels
            
        Returns:
            Compressed audio data
        """
        if self.level == CompressionLevel.NONE:
            return audio_data
        
        try:
            # Simple compression using zlib for now
            # In production, would use audio-specific codecs
            compressed = zlib.compress(audio_data, level=self._get_zlib_level())
            return compressed
            
        except Exception as e:
            logger.error(f"Audio compression failed: {e}")
            return audio_data
    
    def _get_zlib_level(self) -> int:
        """Get zlib compression level from CompressionLevel."""
        level_map = {
            CompressionLevel.NONE: 0,
            CompressionLevel.LOW: 3,
            CompressionLevel.MEDIUM: 6,
            CompressionLevel.HIGH: 9,
            CompressionLevel.ADAPTIVE: 6
        }
        return level_map.get(self.level, 6)