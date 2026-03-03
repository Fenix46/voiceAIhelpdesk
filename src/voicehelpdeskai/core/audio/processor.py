"""Advanced audio processing with real-time capabilities."""

import io
import threading
import time
from collections import deque
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, List, Callable

import numpy as np
import pyaudio
import soundfile as sf
from pydub import AudioSegment
from loguru import logger

try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    logger.warning("noisereduce not available - noise reduction will be disabled")

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa not available - advanced resampling will be disabled")

from voicehelpdeskai.config.manager import get_config_manager
from voicehelpdeskai.core.audio.exceptions import (
    AudioDeviceError,
    AudioFormatError,
    AudioProcessingError,
    NoiseReductionError,
    ResamplingError,
)


class CircularBuffer:
    """Thread-safe circular buffer for audio data."""
    
    def __init__(self, max_size: int):
        """Initialize circular buffer.
        
        Args:
            max_size: Maximum buffer size in samples
        """
        self.max_size = max_size
        self.buffer = np.zeros(max_size, dtype=np.float32)
        self.head = 0
        self.tail = 0
        self.count = 0
        self.lock = threading.RLock()
    
    def write(self, data: np.ndarray) -> int:
        """Write data to buffer.
        
        Args:
            data: Audio data to write
            
        Returns:
            Number of samples written
        """
        with self.lock:
            data = np.asarray(data, dtype=np.float32)
            samples_to_write = min(len(data), self.max_size - self.count)
            
            if samples_to_write == 0:
                return 0
            
            # Handle wrap-around
            if self.head + samples_to_write <= self.max_size:
                self.buffer[self.head:self.head + samples_to_write] = data[:samples_to_write]
            else:
                # Split write
                first_part = self.max_size - self.head
                self.buffer[self.head:] = data[:first_part]
                self.buffer[:samples_to_write - first_part] = data[first_part:samples_to_write]
            
            self.head = (self.head + samples_to_write) % self.max_size
            self.count += samples_to_write
            
            return samples_to_write
    
    def read(self, num_samples: int) -> np.ndarray:
        """Read data from buffer.
        
        Args:
            num_samples: Number of samples to read
            
        Returns:
            Audio data array
        """
        with self.lock:
            samples_to_read = min(num_samples, self.count)
            
            if samples_to_read == 0:
                return np.array([], dtype=np.float32)
            
            result = np.zeros(samples_to_read, dtype=np.float32)
            
            # Handle wrap-around
            if self.tail + samples_to_read <= self.max_size:
                result = self.buffer[self.tail:self.tail + samples_to_read].copy()
            else:
                # Split read
                first_part = self.max_size - self.tail
                result[:first_part] = self.buffer[self.tail:]
                result[first_part:] = self.buffer[:samples_to_read - first_part]
            
            self.tail = (self.tail + samples_to_read) % self.max_size
            self.count -= samples_to_read
            
            return result
    
    def peek(self, num_samples: int) -> np.ndarray:
        """Peek at data without removing from buffer.
        
        Args:
            num_samples: Number of samples to peek
            
        Returns:
            Audio data array
        """
        with self.lock:
            samples_to_read = min(num_samples, self.count)
            
            if samples_to_read == 0:
                return np.array([], dtype=np.float32)
            
            result = np.zeros(samples_to_read, dtype=np.float32)
            
            # Handle wrap-around
            if self.tail + samples_to_read <= self.max_size:
                result = self.buffer[self.tail:self.tail + samples_to_read].copy()
            else:
                # Split read
                first_part = self.max_size - self.tail
                result[:first_part] = self.buffer[self.tail:]
                result[first_part:] = self.buffer[:samples_to_read - first_part]
            
            return result
    
    @property
    def available(self) -> int:
        """Get number of samples available for reading."""
        with self.lock:
            return self.count
    
    @property 
    def free_space(self) -> int:
        """Get number of samples that can be written."""
        with self.lock:
            return self.max_size - self.count
    
    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.head = 0
            self.tail = 0
            self.count = 0


class AudioProcessor:
    """Advanced audio processor with real-time capabilities."""
    
    def __init__(self, config_manager=None):
        """Initialize audio processor.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or get_config_manager()
        self.settings = self.config_manager.get_settings()
        self.audio_config = self.settings.audio
        
        # PyAudio instance
        self.pyaudio = None
        self.input_stream = None
        self.output_stream = None
        
        # Audio parameters
        self.sample_rate = self.audio_config.sample_rate
        self.channels = self.audio_config.channels
        self.chunk_size = self.audio_config.chunk_size
        self.format = pyaudio.paFloat32
        
        # Circular buffer for streaming
        buffer_size = self.sample_rate * 10  # 10 seconds buffer
        self.input_buffer = CircularBuffer(buffer_size)
        self.output_buffer = CircularBuffer(buffer_size)
        
        # Processing state
        self.is_recording = False
        self.is_playing = False
        self.recording_thread = None
        self.playback_thread = None
        
        # Callbacks
        self.audio_callback: Optional[Callable[[np.ndarray], None]] = None
        
        # Statistics
        self.stats = {
            "total_frames_processed": 0,
            "total_bytes_processed": 0,
            "processing_errors": 0,
            "last_processing_time": 0.0,
            "average_processing_time": 0.0,
        }
        
        # Noise reduction
        self.noise_profile = None
        self.noise_reduction_enabled = (
            NOISEREDUCE_AVAILABLE and self.audio_config.enable_noise_reduction
        )
        
        logger.info("AudioProcessor initialized", 
                   sample_rate=self.sample_rate,
                   channels=self.channels,
                   chunk_size=self.chunk_size,
                   noise_reduction=self.noise_reduction_enabled)
    
    def initialize_pyaudio(self):
        """Initialize PyAudio instance."""
        if self.pyaudio is not None:
            return
        
        try:
            self.pyaudio = pyaudio.PyAudio()
            logger.info("PyAudio initialized successfully")
            
            # Log available devices
            self._log_audio_devices()
            
        except Exception as e:
            raise AudioDeviceError(f"Failed to initialize PyAudio: {e}")
    
    def _log_audio_devices(self):
        """Log available audio devices."""
        if not self.pyaudio:
            return
        
        device_count = self.pyaudio.get_device_count()
        logger.info(f"Found {device_count} audio devices:")
        
        for i in range(device_count):
            try:
                device_info = self.pyaudio.get_device_info_by_index(i)
                logger.debug(f"  Device {i}: {device_info['name']} "
                           f"(in: {device_info['maxInputChannels']}, "
                           f"out: {device_info['maxOutputChannels']})")
            except Exception as e:
                logger.warning(f"Could not get info for device {i}: {e}")
    
    def get_default_input_device(self) -> Optional[int]:
        """Get default input device index."""
        if not self.pyaudio:
            self.initialize_pyaudio()
        
        try:
            default_device = self.pyaudio.get_default_input_device_info()
            return default_device['index']
        except Exception as e:
            logger.warning(f"Could not get default input device: {e}")
            return None
    
    def get_default_output_device(self) -> Optional[int]:
        """Get default output device index."""
        if not self.pyaudio:
            self.initialize_pyaudio()
        
        try:
            default_device = self.pyaudio.get_default_output_device_info()
            return default_device['index']
        except Exception as e:
            logger.warning(f"Could not get default output device: {e}")
            return None
    
    def start_recording(self, 
                       device_index: Optional[int] = None,
                       callback: Optional[Callable[[np.ndarray], None]] = None) -> bool:
        """Start audio recording.
        
        Args:
            device_index: Input device index (None for default)
            callback: Callback function for audio data
            
        Returns:
            True if recording started successfully
        """
        if self.is_recording:
            logger.warning("Recording is already active")
            return False
        
        try:
            self.initialize_pyaudio()
            
            if device_index is None:
                device_index = self.get_default_input_device()
            
            self.audio_callback = callback
            
            # Create input stream
            self.input_stream = self.pyaudio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._input_callback,
                start=False
            )
            
            # Start recording thread
            self.is_recording = True
            self.input_stream.start_stream()
            
            logger.info("Audio recording started", 
                       device_index=device_index,
                       sample_rate=self.sample_rate)
            
            return True
            
        except Exception as e:
            self.is_recording = False
            raise AudioDeviceError(f"Failed to start recording: {e}")
    
    def stop_recording(self):
        """Stop audio recording."""
        if not self.is_recording:
            return
        
        try:
            self.is_recording = False
            
            if self.input_stream:
                self.input_stream.stop_stream()
                self.input_stream.close()
                self.input_stream = None
            
            logger.info("Audio recording stopped")
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
    
    def _input_callback(self, in_data, frame_count, time_info, status):
        """PyAudio input stream callback."""
        try:
            # Convert bytes to numpy array
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            
            # Store in circular buffer
            self.input_buffer.write(audio_data)
            
            # Process audio if callback is set
            if self.audio_callback:
                processed_data = self.process_audio_chunk(audio_data)
                self.audio_callback(processed_data)
            
            # Update statistics
            self.stats["total_frames_processed"] += frame_count
            self.stats["total_bytes_processed"] += len(in_data)
            
            return (None, pyaudio.paContinue)
            
        except Exception as e:
            logger.error(f"Error in input callback: {e}")
            self.stats["processing_errors"] += 1
            return (None, pyaudio.paAbort)
    
    def read_audio_chunk(self, num_samples: Optional[int] = None) -> np.ndarray:
        """Read audio chunk from input buffer.
        
        Args:
            num_samples: Number of samples to read (None for chunk_size)
            
        Returns:
            Audio data array
        """
        if num_samples is None:
            num_samples = self.chunk_size
        
        return self.input_buffer.read(num_samples)
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> np.ndarray:
        """Process audio chunk with noise reduction and normalization.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Processed audio data
        """
        start_time = time.time()
        
        try:
            # Ensure correct data type
            audio_data = np.asarray(audio_data, dtype=np.float32)
            
            # Apply gain control if enabled
            if self.audio_config.enable_auto_gain:
                audio_data = self._apply_auto_gain(audio_data)
            
            # Apply noise reduction if enabled
            if self.noise_reduction_enabled and len(audio_data) > 0:
                audio_data = self._apply_noise_reduction(audio_data)
            
            # Normalize if enabled
            if self.audio_config.normalize_audio:
                audio_data = self._normalize_audio(audio_data)
            
            # Update timing statistics
            processing_time = time.time() - start_time
            self.stats["last_processing_time"] = processing_time
            self._update_average_processing_time(processing_time)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            self.stats["processing_errors"] += 1
            return audio_data  # Return original data on error
    
    def _apply_auto_gain(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply automatic gain control.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Gain-adjusted audio data
        """
        if len(audio_data) == 0:
            return audio_data
        
        # Calculate RMS
        rms = np.sqrt(np.mean(audio_data ** 2))
        
        if rms > 0:
            # Target RMS level (adjustable)
            target_rms = 0.1
            gain = target_rms / rms
            
            # Limit gain to prevent distortion
            gain = np.clip(gain, 0.1, 10.0)
            
            return audio_data * gain
        
        return audio_data
    
    def _apply_noise_reduction(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply noise reduction using noisereduce.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Noise-reduced audio data
        """
        if not NOISEREDUCE_AVAILABLE or len(audio_data) == 0:
            return audio_data
        
        try:
            # Apply noise reduction
            reduced_data = nr.reduce_noise(
                y=audio_data,
                sr=self.sample_rate,
                stationary=True,
                prop_decrease=self.audio_config.noise_reduction_strength
            )
            
            return reduced_data.astype(np.float32)
            
        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return audio_data
    
    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio data.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Normalized audio data
        """
        if len(audio_data) == 0:
            return audio_data
        
        # Find peak
        peak = np.max(np.abs(audio_data))
        
        if peak > 0:
            # Normalize to [-1, 1] range with some headroom
            return audio_data / peak * 0.95
        
        return audio_data
    
    def _update_average_processing_time(self, new_time: float):
        """Update rolling average processing time."""
        alpha = 0.1  # Smoothing factor
        if self.stats["average_processing_time"] == 0:
            self.stats["average_processing_time"] = new_time
        else:
            self.stats["average_processing_time"] = (
                alpha * new_time + 
                (1 - alpha) * self.stats["average_processing_time"]
            )
    
    def convert_format(self, 
                      audio_data: np.ndarray,
                      target_format: str,
                      input_sample_rate: Optional[int] = None) -> bytes:
        """Convert audio data to specified format.
        
        Args:
            audio_data: Input audio data
            target_format: Target format (wav, mp3, etc.)
            input_sample_rate: Input sample rate (uses default if None)
            
        Returns:
            Converted audio data as bytes
        """
        if input_sample_rate is None:
            input_sample_rate = self.sample_rate
        
        try:
            # Ensure audio is in correct format
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Create AudioSegment from numpy array
            audio_segment = self._numpy_to_audiosegment(
                audio_data, input_sample_rate
            )
            
            # Convert to target format
            output_buffer = io.BytesIO()
            
            if target_format.lower() == 'wav':
                audio_segment.export(output_buffer, format="wav")
            elif target_format.lower() == 'mp3':
                audio_segment.export(output_buffer, format="mp3")
            elif target_format.lower() == 'pcm':
                return audio_data.tobytes()
            else:
                raise AudioFormatError(f"Unsupported format: {target_format}")
            
            return output_buffer.getvalue()
            
        except Exception as e:
            raise AudioFormatError(f"Format conversion failed: {e}")
    
    def _numpy_to_audiosegment(self, 
                              audio_data: np.ndarray, 
                              sample_rate: int) -> AudioSegment:
        """Convert numpy array to AudioSegment.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate
            
        Returns:
            AudioSegment instance
        """
        # Convert to 16-bit integers for AudioSegment
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # Create AudioSegment
        audio_segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sample_rate,
            sample_width=audio_int16.dtype.itemsize,
            channels=self.channels
        )
        
        return audio_segment
    
    def resample_audio(self, 
                      audio_data: np.ndarray,
                      original_sr: int,
                      target_sr: int) -> np.ndarray:
        """Resample audio data.
        
        Args:
            audio_data: Input audio data
            original_sr: Original sample rate
            target_sr: Target sample rate
            
        Returns:
            Resampled audio data
        """
        if original_sr == target_sr:
            return audio_data
        
        try:
            if LIBROSA_AVAILABLE:
                # Use librosa for high-quality resampling
                resampled = librosa.resample(
                    audio_data, 
                    orig_sr=original_sr,
                    target_sr=target_sr,
                    res_type='soxr_hq'
                )
                return resampled.astype(np.float32)
            else:
                # Fallback to simple linear interpolation
                ratio = target_sr / original_sr
                new_length = int(len(audio_data) * ratio)
                
                # Simple linear interpolation
                old_indices = np.linspace(0, len(audio_data) - 1, new_length)
                resampled = np.interp(old_indices, np.arange(len(audio_data)), audio_data)
                
                return resampled.astype(np.float32)
                
        except Exception as e:
            raise ResamplingError(f"Resampling failed: {e}")
    
    def save_audio(self, 
                   audio_data: np.ndarray,
                   filename: Union[str, Path],
                   sample_rate: Optional[int] = None) -> bool:
        """Save audio data to file.
        
        Args:
            audio_data: Audio data to save
            filename: Output filename
            sample_rate: Sample rate (uses default if None)
            
        Returns:
            True if saved successfully
        """
        if sample_rate is None:
            sample_rate = self.sample_rate
        
        try:
            filename = Path(filename)
            filename.parent.mkdir(parents=True, exist_ok=True)
            
            # Save using soundfile
            sf.write(str(filename), audio_data, sample_rate)
            
            logger.info(f"Audio saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            return False
    
    def load_audio(self, 
                   filename: Union[str, Path],
                   target_sample_rate: Optional[int] = None) -> Tuple[np.ndarray, int]:
        """Load audio from file.
        
        Args:
            filename: Input filename
            target_sample_rate: Target sample rate for resampling
            
        Returns:
            Tuple of (audio_data, sample_rate)
        """
        try:
            filename = Path(filename)
            
            if not filename.exists():
                raise FileNotFoundError(f"Audio file not found: {filename}")
            
            # Load using soundfile
            audio_data, sample_rate = sf.read(str(filename), dtype=np.float32)
            
            # Resample if needed
            if target_sample_rate and target_sample_rate != sample_rate:
                audio_data = self.resample_audio(
                    audio_data, sample_rate, target_sample_rate
                )
                sample_rate = target_sample_rate
            
            logger.info(f"Audio loaded from {filename}", 
                       sample_rate=sample_rate,
                       duration=len(audio_data) / sample_rate)
            
            return audio_data, sample_rate
            
        except Exception as e:
            raise AudioProcessingError(f"Failed to load audio: {e}")
    
    def get_stats(self) -> Dict:
        """Get processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {
            "total_frames_processed": 0,
            "total_bytes_processed": 0,
            "processing_errors": 0,
            "last_processing_time": 0.0,
            "average_processing_time": 0.0,
        }
    
    def calibrate_noise_profile(self, duration: float = 2.0) -> bool:
        """Calibrate noise profile for noise reduction.
        
        Args:
            duration: Duration in seconds to record noise
            
        Returns:
            True if calibration successful
        """
        if not NOISEREDUCE_AVAILABLE:
            logger.warning("Noise reduction not available")
            return False
        
        try:
            logger.info(f"Recording {duration}s of background noise for calibration...")
            
            # Record background noise
            noise_samples = int(self.sample_rate * duration)
            noise_data = []
            
            # Start temporary recording
            temp_callback = lambda data: noise_data.extend(data)
            self.start_recording(callback=temp_callback)
            
            time.sleep(duration)
            self.stop_recording()
            
            if len(noise_data) > 0:
                self.noise_profile = np.array(noise_data, dtype=np.float32)
                logger.info("Noise profile calibrated successfully")
                return True
            else:
                logger.warning("No noise data collected")
                return False
                
        except Exception as e:
            logger.error(f"Noise calibration failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.stop_recording()
            
            if self.pyaudio:
                self.pyaudio.terminate()
                self.pyaudio = None
            
            logger.info("AudioProcessor cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def __del__(self):
        """Destructor."""
        try:
            self.cleanup()
        except:
            pass