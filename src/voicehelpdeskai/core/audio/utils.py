"""Audio processing utilities and helper functions."""

import io
import math
import os
import tempfile
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from loguru import logger

try:
    import scipy.signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available - advanced filtering will be disabled")

try:
    from pydub import AudioSegment
    from pydub.utils import make_chunks
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available - format conversion will be limited")

from voicehelpdeskai.core.audio.exceptions import (
    AudioProcessingError,
    AudioFormatError,
    ResamplingError,
)


class AudioFormat:
    """Audio format utilities and constants."""
    
    # Supported formats
    SUPPORTED_FORMATS = ['wav', 'mp3', 'flac', 'ogg', 'm4a', 'aac']
    
    # Sample rate constants
    SAMPLE_RATES = {
        'telephone': 8000,
        'narrowband': 8000,
        'wideband': 16000,
        'cd': 44100,
        'professional': 48000,
        'high_res': 96000,
    }
    
    # Bit depth constants
    BIT_DEPTHS = {
        'int16': np.int16,
        'int24': np.int32,  # Stored as int32
        'int32': np.int32,
        'float32': np.float32,
        'float64': np.float64,
    }
    
    @staticmethod
    def get_format_info(file_path: Union[str, Path]) -> Dict[str, Union[str, int, float]]:
        """Get audio format information from file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Dictionary with format information
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        try:
            if PYDUB_AVAILABLE:
                audio = AudioSegment.from_file(str(file_path))
                return {
                    'format': file_path.suffix.lower().lstrip('.'),
                    'channels': audio.channels,
                    'sample_rate': audio.frame_rate,
                    'duration': len(audio) / 1000.0,  # Convert to seconds
                    'frame_count': audio.frame_count(),
                    'sample_width': audio.sample_width,
                    'bit_depth': audio.sample_width * 8,
                }
            else:
                # Fallback for WAV files only
                if file_path.suffix.lower() != '.wav':
                    raise AudioFormatError("Only WAV format supported without pydub")
                
                with wave.open(str(file_path), 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    sample_rate = wav_file.getframerate()
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    
                    return {
                        'format': 'wav',
                        'channels': channels,
                        'sample_rate': sample_rate,
                        'duration': frames / sample_rate,
                        'frame_count': frames,
                        'sample_width': sample_width,
                        'bit_depth': sample_width * 8,
                    }
                    
        except Exception as e:
            raise AudioFormatError(f"Failed to get format info: {e}")


class AudioConverter:
    """Audio format conversion utilities."""
    
    @staticmethod
    def convert_sample_rate(audio_data: np.ndarray,
                           original_sr: int,
                           target_sr: int,
                           method: str = 'linear') -> np.ndarray:
        """Convert audio sample rate.
        
        Args:
            audio_data: Input audio data
            original_sr: Original sample rate
            target_sr: Target sample rate
            method: Resampling method ('linear', 'cubic', 'sinc')
            
        Returns:
            Resampled audio data
        """
        if original_sr == target_sr:
            return audio_data
        
        try:
            if SCIPY_AVAILABLE and method == 'sinc':
                # High-quality sinc interpolation
                resampled = scipy.signal.resample(
                    audio_data, 
                    int(len(audio_data) * target_sr / original_sr)
                )
                return resampled.astype(np.float32)
            
            else:
                # Linear interpolation fallback
                ratio = target_sr / original_sr
                new_length = int(len(audio_data) * ratio)
                
                if method == 'cubic' and SCIPY_AVAILABLE:
                    from scipy import interpolate
                    f = interpolate.interp1d(
                        np.arange(len(audio_data)), 
                        audio_data, 
                        kind='cubic',
                        bounds_error=False,
                        fill_value='extrapolate'
                    )
                    new_indices = np.linspace(0, len(audio_data) - 1, new_length)
                    resampled = f(new_indices)
                else:
                    # Simple linear interpolation
                    old_indices = np.linspace(0, len(audio_data) - 1, new_length)
                    resampled = np.interp(old_indices, np.arange(len(audio_data)), audio_data)
                
                return resampled.astype(np.float32)
                
        except Exception as e:
            raise ResamplingError(f"Sample rate conversion failed: {e}")
    
    @staticmethod
    def convert_channels(audio_data: np.ndarray, 
                        target_channels: int) -> np.ndarray:
        """Convert audio channel count.
        
        Args:
            audio_data: Input audio data (shape: [samples] or [samples, channels])
            target_channels: Target number of channels
            
        Returns:
            Audio data with target channel count
        """
        try:
            # Handle 1D input
            if audio_data.ndim == 1:
                current_channels = 1
                audio_data = audio_data.reshape(-1, 1)
            else:
                current_channels = audio_data.shape[1]
            
            if current_channels == target_channels:
                return audio_data.squeeze() if target_channels == 1 else audio_data
            
            if target_channels == 1:
                # Convert to mono by averaging channels
                mono_data = np.mean(audio_data, axis=1)
                return mono_data
            
            elif current_channels == 1 and target_channels == 2:
                # Convert mono to stereo by duplicating
                stereo_data = np.column_stack([audio_data, audio_data])
                return stereo_data
            
            elif target_channels == 2 and current_channels > 2:
                # Mix down to stereo
                stereo_data = np.column_stack([
                    np.mean(audio_data[:, :current_channels//2], axis=1),
                    np.mean(audio_data[:, current_channels//2:], axis=1)
                ])
                return stereo_data
            
            else:
                raise AudioFormatError(
                    f"Unsupported channel conversion: {current_channels} -> {target_channels}"
                )
                
        except Exception as e:
            raise AudioFormatError(f"Channel conversion failed: {e}")
    
    @staticmethod
    def convert_bit_depth(audio_data: np.ndarray, 
                         target_dtype: Union[str, np.dtype]) -> np.ndarray:
        """Convert audio bit depth.
        
        Args:
            audio_data: Input audio data
            target_dtype: Target data type
            
        Returns:
            Audio data with target bit depth
        """
        try:
            if isinstance(target_dtype, str):
                target_dtype = AudioFormat.BIT_DEPTHS.get(target_dtype, np.float32)
            
            # Current data type
            current_dtype = audio_data.dtype
            
            if current_dtype == target_dtype:
                return audio_data
            
            # Normalize to [-1, 1] range first
            if np.issubdtype(current_dtype, np.integer):
                # Integer to float
                info = np.iinfo(current_dtype)
                normalized = audio_data.astype(np.float64) / max(abs(info.min), info.max)
            else:
                # Float (assume already normalized)
                normalized = audio_data.astype(np.float64)
                # Clip to [-1, 1] range
                normalized = np.clip(normalized, -1.0, 1.0)
            
            # Convert to target type
            if np.issubdtype(target_dtype, np.integer):
                # Float to integer
                info = np.iinfo(target_dtype)
                scaled = normalized * max(abs(info.min), info.max)
                return scaled.astype(target_dtype)
            else:
                # Float to float
                return normalized.astype(target_dtype)
                
        except Exception as e:
            raise AudioFormatError(f"Bit depth conversion failed: {e}")


class AudioFilter:
    """Audio filtering utilities."""
    
    @staticmethod
    def apply_highpass_filter(audio_data: np.ndarray,
                             cutoff_freq: float,
                             sample_rate: int,
                             order: int = 5) -> np.ndarray:
        """Apply high-pass filter to remove low frequencies.
        
        Args:
            audio_data: Input audio data
            cutoff_freq: Cutoff frequency in Hz
            sample_rate: Audio sample rate
            order: Filter order
            
        Returns:
            Filtered audio data
        """
        if not SCIPY_AVAILABLE:
            logger.warning("scipy not available - high-pass filter disabled")
            return audio_data
        
        try:
            # Design high-pass filter
            nyquist = sample_rate / 2
            normal_cutoff = cutoff_freq / nyquist
            
            b, a = scipy.signal.butter(order, normal_cutoff, btype='high', analog=False)
            
            # Apply filter
            filtered_data = scipy.signal.filtfilt(b, a, audio_data)
            
            return filtered_data.astype(audio_data.dtype)
            
        except Exception as e:
            logger.error(f"High-pass filter failed: {e}")
            return audio_data
    
    @staticmethod
    def apply_lowpass_filter(audio_data: np.ndarray,
                            cutoff_freq: float,
                            sample_rate: int,
                            order: int = 5) -> np.ndarray:
        """Apply low-pass filter to remove high frequencies.
        
        Args:
            audio_data: Input audio data
            cutoff_freq: Cutoff frequency in Hz
            sample_rate: Audio sample rate
            order: Filter order
            
        Returns:
            Filtered audio data
        """
        if not SCIPY_AVAILABLE:
            logger.warning("scipy not available - low-pass filter disabled")
            return audio_data
        
        try:
            # Design low-pass filter
            nyquist = sample_rate / 2
            normal_cutoff = cutoff_freq / nyquist
            
            b, a = scipy.signal.butter(order, normal_cutoff, btype='low', analog=False)
            
            # Apply filter
            filtered_data = scipy.signal.filtfilt(b, a, audio_data)
            
            return filtered_data.astype(audio_data.dtype)
            
        except Exception as e:
            logger.error(f"Low-pass filter failed: {e}")
            return audio_data
    
    @staticmethod
    def apply_bandpass_filter(audio_data: np.ndarray,
                             low_freq: float,
                             high_freq: float,
                             sample_rate: int,
                             order: int = 5) -> np.ndarray:
        """Apply band-pass filter.
        
        Args:
            audio_data: Input audio data
            low_freq: Low cutoff frequency in Hz
            high_freq: High cutoff frequency in Hz
            sample_rate: Audio sample rate
            order: Filter order
            
        Returns:
            Filtered audio data
        """
        if not SCIPY_AVAILABLE:
            logger.warning("scipy not available - band-pass filter disabled")
            return audio_data
        
        try:
            # Design band-pass filter
            nyquist = sample_rate / 2
            low = low_freq / nyquist
            high = high_freq / nyquist
            
            b, a = scipy.signal.butter(order, [low, high], btype='band', analog=False)
            
            # Apply filter
            filtered_data = scipy.signal.filtfilt(b, a, audio_data)
            
            return filtered_data.astype(audio_data.dtype)
            
        except Exception as e:
            logger.error(f"Band-pass filter failed: {e}")
            return audio_data


class AudioAnalyzer:
    """Audio analysis utilities."""
    
    @staticmethod
    def calculate_rms(audio_data: np.ndarray) -> float:
        """Calculate RMS (Root Mean Square) energy.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            RMS energy value
        """
        return float(np.sqrt(np.mean(audio_data ** 2)))
    
    @staticmethod
    def calculate_peak(audio_data: np.ndarray) -> float:
        """Calculate peak amplitude.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Peak amplitude value
        """
        return float(np.max(np.abs(audio_data)))
    
    @staticmethod
    def calculate_snr(signal: np.ndarray, noise: np.ndarray) -> float:
        """Calculate Signal-to-Noise Ratio.
        
        Args:
            signal: Signal audio data
            noise: Noise audio data
            
        Returns:
            SNR in dB
        """
        signal_power = np.mean(signal ** 2)
        noise_power = np.mean(noise ** 2)
        
        if noise_power == 0:
            return float('inf')
        
        snr_linear = signal_power / noise_power
        snr_db = 10 * np.log10(snr_linear)
        
        return float(snr_db)
    
    @staticmethod
    def detect_clipping(audio_data: np.ndarray, threshold: float = 0.99) -> Dict[str, Union[bool, int, float]]:
        """Detect audio clipping.
        
        Args:
            audio_data: Input audio data
            threshold: Clipping threshold (0-1)
            
        Returns:
            Dictionary with clipping information
        """
        abs_data = np.abs(audio_data)
        clipped_samples = np.sum(abs_data >= threshold)
        total_samples = len(audio_data)
        
        clipping_ratio = clipped_samples / total_samples if total_samples > 0 else 0
        
        return {
            'has_clipping': clipped_samples > 0,
            'clipped_samples': int(clipped_samples),
            'total_samples': int(total_samples),
            'clipping_ratio': float(clipping_ratio),
            'peak_value': float(np.max(abs_data)),
        }
    
    @staticmethod
    def calculate_spectral_centroid(audio_data: np.ndarray, 
                                  sample_rate: int,
                                  window_size: int = 2048) -> np.ndarray:
        """Calculate spectral centroid over time.
        
        Args:
            audio_data: Input audio data
            sample_rate: Audio sample rate
            window_size: FFT window size
            
        Returns:
            Array of spectral centroid values
        """
        if not SCIPY_AVAILABLE:
            logger.warning("scipy not available - spectral analysis disabled")
            return np.array([])
        
        try:
            # Calculate spectrogram
            frequencies, times, spectrogram = scipy.signal.spectrogram(
                audio_data, 
                fs=sample_rate,
                window='hann',
                nperseg=window_size,
                noverlap=window_size//2
            )
            
            # Calculate spectral centroid
            magnitude_spectrum = np.abs(spectrogram)
            
            # Weighted average of frequencies
            centroids = []
            for frame in magnitude_spectrum.T:
                if np.sum(frame) > 0:
                    centroid = np.sum(frequencies * frame) / np.sum(frame)
                    centroids.append(centroid)
                else:
                    centroids.append(0.0)
            
            return np.array(centroids)
            
        except Exception as e:
            logger.error(f"Spectral centroid calculation failed: {e}")
            return np.array([])
    
    @staticmethod
    def calculate_zero_crossing_rate(audio_data: np.ndarray, 
                                   frame_length: int = 2048) -> np.ndarray:
        """Calculate zero crossing rate over time.
        
        Args:
            audio_data: Input audio data
            frame_length: Frame length for analysis
            
        Returns:
            Array of zero crossing rates
        """
        try:
            # Ensure audio is 1D
            if audio_data.ndim > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            zcrs = []
            
            for i in range(0, len(audio_data) - frame_length + 1, frame_length // 2):
                frame = audio_data[i:i + frame_length]
                
                # Count zero crossings
                zero_crossings = np.sum(np.diff(np.signbit(frame)))
                zcr = zero_crossings / len(frame)
                zcrs.append(zcr)
            
            return np.array(zcrs)
            
        except Exception as e:
            logger.error(f"Zero crossing rate calculation failed: {e}")
            return np.array([])


class AudioNormalizer:
    """Audio normalization utilities."""
    
    @staticmethod
    def normalize_peak(audio_data: np.ndarray, target_peak: float = 1.0) -> np.ndarray:
        """Normalize audio to target peak level.
        
        Args:
            audio_data: Input audio data
            target_peak: Target peak level (0-1)
            
        Returns:
            Normalized audio data
        """
        peak = np.max(np.abs(audio_data))
        
        if peak == 0:
            return audio_data
        
        gain = target_peak / peak
        return audio_data * gain
    
    @staticmethod
    def normalize_rms(audio_data: np.ndarray, target_rms: float = 0.1) -> np.ndarray:
        """Normalize audio to target RMS level.
        
        Args:
            audio_data: Input audio data
            target_rms: Target RMS level
            
        Returns:
            Normalized audio data
        """
        rms = np.sqrt(np.mean(audio_data ** 2))
        
        if rms == 0:
            return audio_data
        
        gain = target_rms / rms
        return audio_data * gain
    
    @staticmethod
    def apply_dynamic_range_compression(audio_data: np.ndarray,
                                      threshold: float = 0.5,
                                      ratio: float = 4.0,
                                      attack_time: float = 0.003,
                                      release_time: float = 0.1,
                                      sample_rate: int = 16000) -> np.ndarray:
        """Apply dynamic range compression.
        
        Args:
            audio_data: Input audio data
            threshold: Compression threshold (0-1)
            ratio: Compression ratio
            attack_time: Attack time in seconds
            release_time: Release time in seconds
            sample_rate: Audio sample rate
            
        Returns:
            Compressed audio data
        """
        try:
            # Convert times to samples
            attack_samples = int(attack_time * sample_rate)
            release_samples = int(release_time * sample_rate)
            
            # Calculate envelope
            envelope = np.abs(audio_data)
            
            # Smooth envelope
            if SCIPY_AVAILABLE:
                from scipy.ndimage import uniform_filter1d
                envelope = uniform_filter1d(envelope, size=attack_samples)
            
            # Apply compression
            compressed = np.copy(audio_data)
            
            for i in range(len(audio_data)):
                if envelope[i] > threshold:
                    # Calculate gain reduction
                    over_threshold = envelope[i] - threshold
                    gain_reduction = 1.0 - (over_threshold * (1.0 - 1.0/ratio))
                    compressed[i] = audio_data[i] * gain_reduction
            
            return compressed
            
        except Exception as e:
            logger.error(f"Dynamic range compression failed: {e}")
            return audio_data


class AudioValidator:
    """Audio validation utilities."""
    
    @staticmethod
    def validate_sample_rate(sample_rate: int) -> bool:
        """Validate sample rate.
        
        Args:
            sample_rate: Sample rate to validate
            
        Returns:
            True if valid
        """
        valid_rates = [8000, 11025, 16000, 22050, 44100, 48000, 88200, 96000, 192000]
        return sample_rate in valid_rates
    
    @staticmethod
    def validate_audio_data(audio_data: np.ndarray) -> Dict[str, Union[bool, str, float]]:
        """Validate audio data array.
        
        Args:
            audio_data: Audio data to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': {}
        }
        
        try:
            # Check if it's a numpy array
            if not isinstance(audio_data, np.ndarray):
                result['valid'] = False
                result['errors'].append("Audio data must be a numpy array")
                return result
            
            # Check dimensions
            if audio_data.ndim > 2:
                result['valid'] = False
                result['errors'].append("Audio data must be 1D or 2D")
                return result
            
            # Check for empty data
            if audio_data.size == 0:
                result['valid'] = False
                result['errors'].append("Audio data is empty")
                return result
            
            # Check data type
            if not np.issubdtype(audio_data.dtype, np.floating) and not np.issubdtype(audio_data.dtype, np.integer):
                result['warnings'].append(f"Unusual data type: {audio_data.dtype}")
            
            # Check for NaN or infinite values
            if np.any(np.isnan(audio_data)):
                result['valid'] = False
                result['errors'].append("Audio data contains NaN values")
            
            if np.any(np.isinf(audio_data)):
                result['valid'] = False
                result['errors'].append("Audio data contains infinite values")
            
            # Check dynamic range
            peak = np.max(np.abs(audio_data))
            if peak == 0:
                result['warnings'].append("Audio data is silent (all zeros)")
            elif peak > 10:
                result['warnings'].append(f"Very high peak value: {peak}")
            
            # Add info
            result['info'] = {
                'shape': audio_data.shape,
                'dtype': str(audio_data.dtype),
                'peak': float(peak),
                'rms': float(np.sqrt(np.mean(audio_data ** 2))),
                'duration_samples': len(audio_data) if audio_data.ndim == 1 else audio_data.shape[0],
            }
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Validation error: {e}")
        
        return result
    
    @staticmethod
    def check_audio_quality(audio_data: np.ndarray, 
                          sample_rate: int) -> Dict[str, Union[bool, float, str]]:
        """Check audio quality metrics.
        
        Args:
            audio_data: Audio data
            sample_rate: Sample rate
            
        Returns:
            Dictionary with quality metrics
        """
        result = {
            'overall_quality': 'good',
            'issues': [],
            'metrics': {}
        }
        
        try:
            # Calculate metrics
            rms = AudioAnalyzer.calculate_rms(audio_data)
            peak = AudioAnalyzer.calculate_peak(audio_data)
            clipping_info = AudioAnalyzer.detect_clipping(audio_data)
            
            result['metrics'] = {
                'rms': rms,
                'peak': peak,
                'dynamic_range': peak / max(rms, 1e-10),
                'clipping_ratio': clipping_info['clipping_ratio'],
            }
            
            # Check for issues
            if clipping_info['has_clipping']:
                result['issues'].append(f"Clipping detected: {clipping_info['clipping_ratio']:.2%} of samples")
                result['overall_quality'] = 'poor'
            
            if rms < 0.001:
                result['issues'].append("Very low signal level")
                if result['overall_quality'] == 'good':
                    result['overall_quality'] = 'fair'
            
            if peak > 0.95:
                result['issues'].append("Signal level very close to maximum")
                if result['overall_quality'] == 'good':
                    result['overall_quality'] = 'fair'
            
            # Check frequency range (if scipy available)
            if SCIPY_AVAILABLE:
                try:
                    freqs, psd = scipy.signal.welch(audio_data, fs=sample_rate)
                    
                    # Check if most energy is in very low frequencies (possible DC offset)
                    low_freq_energy = np.sum(psd[freqs < 100])
                    total_energy = np.sum(psd)
                    
                    if low_freq_energy / total_energy > 0.8:
                        result['issues'].append("Most energy in very low frequencies - possible DC offset")
                        if result['overall_quality'] == 'good':
                            result['overall_quality'] = 'fair'
                            
                except Exception as e:
                    logger.warning(f"Frequency analysis failed: {e}")
            
        except Exception as e:
            result['issues'].append(f"Quality check error: {e}")
            result['overall_quality'] = 'unknown'
        
        return result


def create_silence(duration: float, sample_rate: int, channels: int = 1) -> np.ndarray:
    """Create silent audio data.
    
    Args:
        duration: Duration in seconds
        sample_rate: Sample rate
        channels: Number of channels
        
    Returns:
        Silent audio data
    """
    samples = int(duration * sample_rate)
    
    if channels == 1:
        return np.zeros(samples, dtype=np.float32)
    else:
        return np.zeros((samples, channels), dtype=np.float32)


def fade_in(audio_data: np.ndarray, fade_duration: float, sample_rate: int) -> np.ndarray:
    """Apply fade-in effect to audio.
    
    Args:
        audio_data: Input audio data
        fade_duration: Fade duration in seconds
        sample_rate: Sample rate
        
    Returns:
        Audio data with fade-in effect
    """
    fade_samples = int(fade_duration * sample_rate)
    fade_samples = min(fade_samples, len(audio_data))
    
    if fade_samples <= 0:
        return audio_data
    
    # Create fade curve
    fade_curve = np.linspace(0, 1, fade_samples)
    
    # Apply fade
    result = audio_data.copy()
    if audio_data.ndim == 1:
        result[:fade_samples] *= fade_curve
    else:
        result[:fade_samples] *= fade_curve[:, np.newaxis]
    
    return result


def fade_out(audio_data: np.ndarray, fade_duration: float, sample_rate: int) -> np.ndarray:
    """Apply fade-out effect to audio.
    
    Args:
        audio_data: Input audio data
        fade_duration: Fade duration in seconds
        sample_rate: Sample rate
        
    Returns:
        Audio data with fade-out effect
    """
    fade_samples = int(fade_duration * sample_rate)
    fade_samples = min(fade_samples, len(audio_data))
    
    if fade_samples <= 0:
        return audio_data
    
    # Create fade curve
    fade_curve = np.linspace(1, 0, fade_samples)
    
    # Apply fade
    result = audio_data.copy()
    if audio_data.ndim == 1:
        result[-fade_samples:] *= fade_curve
    else:
        result[-fade_samples:] *= fade_curve[:, np.newaxis]
    
    return result


def mix_audio(audio1: np.ndarray, audio2: np.ndarray, 
              gain1: float = 1.0, gain2: float = 1.0) -> np.ndarray:
    """Mix two audio signals.
    
    Args:
        audio1: First audio signal
        audio2: Second audio signal
        gain1: Gain for first signal
        gain2: Gain for second signal
        
    Returns:
        Mixed audio signal
    """
    # Make signals the same length
    max_length = max(len(audio1), len(audio2))
    
    if len(audio1) < max_length:
        audio1 = np.pad(audio1, (0, max_length - len(audio1)), 'constant')
    
    if len(audio2) < max_length:
        audio2 = np.pad(audio2, (0, max_length - len(audio2)), 'constant')
    
    # Mix with gains
    mixed = audio1 * gain1 + audio2 * gain2
    
    # Prevent clipping
    peak = np.max(np.abs(mixed))
    if peak > 1.0:
        mixed = mixed / peak
    
    return mixed


def save_audio_safely(audio_data: np.ndarray,
                     filename: Union[str, Path],
                     sample_rate: int,
                     backup: bool = True) -> bool:
    """Save audio data safely with backup option.
    
    Args:
        audio_data: Audio data to save
        filename: Output filename
        sample_rate: Sample rate
        backup: Create backup if file exists
        
    Returns:
        True if saved successfully
    """
    try:
        filename = Path(filename)
        
        # Create backup if requested
        if backup and filename.exists():
            backup_name = filename.with_suffix(f'.bak{filename.suffix}')
            filename.rename(backup_name)
            logger.info(f"Created backup: {backup_name}")
        
        # Create directory if it doesn't exist
        filename.parent.mkdir(parents=True, exist_ok=True)
        
        # Validate audio data
        validation = AudioValidator.validate_audio_data(audio_data)
        if not validation['valid']:
            logger.error(f"Invalid audio data: {validation['errors']}")
            return False
        
        # Save to temporary file first
        temp_file = filename.with_suffix(f'.tmp{filename.suffix}')
        
        if PYDUB_AVAILABLE:
            # Use pydub for various formats
            # Convert to AudioSegment
            if audio_data.dtype != np.int16:
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data
            
            audio_segment = AudioSegment(
                audio_int16.tobytes(),
                frame_rate=sample_rate,
                sample_width=audio_int16.dtype.itemsize,
                channels=1 if audio_data.ndim == 1 else audio_data.shape[1]
            )
            
            audio_segment.export(str(temp_file), format=filename.suffix.lstrip('.'))
        
        else:
            # Fallback to wave for WAV files
            if filename.suffix.lower() != '.wav':
                raise AudioFormatError("Only WAV format supported without pydub")
            
            with wave.open(str(temp_file), 'wb') as wav_file:
                wav_file.setnchannels(1 if audio_data.ndim == 1 else audio_data.shape[1])
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                
                # Convert to 16-bit
                if audio_data.dtype != np.int16:
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                else:
                    audio_int16 = audio_data
                
                wav_file.writeframes(audio_int16.tobytes())
        
        # Move temp file to final location
        temp_file.rename(filename)
        
        logger.info(f"Audio saved successfully: {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save audio: {e}")
        return False