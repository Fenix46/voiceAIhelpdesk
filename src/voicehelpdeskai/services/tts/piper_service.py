"""Advanced Piper TTS Service with Italian voice support and SSML processing."""

import asyncio
import hashlib
import io
import json
import os
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, AsyncGenerator
from datetime import datetime, timedelta

import numpy as np
from loguru import logger

try:
    import piper
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    logger.warning("Piper TTS not available - using fallback synthesis")

try:
    import librosa
    import soundfile as sf
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    logger.warning("Audio processing libraries not available - limited functionality")

from voicehelpdeskai.config.manager import get_config_manager


class VoiceGender(Enum):
    """Voice gender options."""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class VoiceLanguage(Enum):
    """Supported voice languages."""
    ITALIAN = "it"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"


class AudioFormat(Enum):
    """Supported audio formats."""
    WAV = "wav"
    MP3 = "mp3" 
    OGG = "ogg"
    FLAC = "flac"


class ProsodyControl(Enum):
    """Prosody control parameters."""
    SPEED = "speed"
    PITCH = "pitch"
    VOLUME = "volume"
    EMPHASIS = "emphasis"


@dataclass
class VoiceModel:
    """Voice model configuration."""
    id: str
    name: str
    language: VoiceLanguage
    gender: VoiceGender
    model_path: Path
    config_path: Optional[Path] = None
    sample_rate: int = 22050
    quality: str = "medium"  # low, medium, high
    description: str = ""
    is_available: bool = False


@dataclass
class ProsodySettings:
    """Prosody control settings."""
    speed: float = 1.0  # 0.5 to 2.0
    pitch: float = 1.0  # 0.5 to 2.0
    volume: float = 1.0  # 0.1 to 2.0
    emphasis_strength: float = 1.2  # Multiplier for emphasized text


@dataclass
class SSMLSettings:
    """SSML processing settings."""
    enable_ssml: bool = True
    enable_breaks: bool = True
    enable_emphasis: bool = True
    enable_prosody: bool = True
    enable_phoneme: bool = True
    break_strength_multiplier: float = 1.0


@dataclass
class TTSRequest:
    """TTS synthesis request."""
    text: str
    voice_id: str
    prosody: ProsodySettings = field(default_factory=ProsodySettings)
    ssml_settings: SSMLSettings = field(default_factory=SSMLSettings)
    audio_format: AudioFormat = AudioFormat.WAV
    streaming: bool = False
    cache_enabled: bool = True
    quality: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSResponse:
    """TTS synthesis response."""
    audio_data: bytes
    sample_rate: int
    duration: float
    format: AudioFormat
    cached: bool = False
    processing_time: float = 0.0
    voice_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class PiperTTSService:
    """Advanced Piper TTS service with Italian voice support."""
    
    def __init__(self,
                 models_dir: str = "./models/piper",
                 cache_dir: str = "./cache/tts",
                 max_cache_size: int = 1000,
                 cache_ttl: int = 86400,
                 enable_caching: bool = True,
                 default_voice: str = "it-riccardo-x-low",
                 fallback_voice: str = "en-us-amy-low"):
        """Initialize Piper TTS service.
        
        Args:
            models_dir: Directory containing Piper voice models
            cache_dir: Directory for caching generated audio
            max_cache_size: Maximum number of cached audio files
            cache_ttl: Cache time-to-live in seconds
            enable_caching: Enable audio response caching
            default_voice: Default voice ID to use
            fallback_voice: Fallback voice if default unavailable
        """
        self.config = get_config_manager().get_config()
        self.models_dir = Path(models_dir)
        self.cache_dir = Path(cache_dir)
        self.max_cache_size = max_cache_size
        self.cache_ttl = cache_ttl
        self.enable_caching = enable_caching
        self.default_voice = default_voice
        self.fallback_voice = fallback_voice
        
        # Create directories
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Voice models
        self.available_voices: Dict[str, VoiceModel] = {}
        self.loaded_voices: Dict[str, Any] = {}  # Loaded Piper voice objects
        
        # Audio cache
        self.audio_cache: Dict[str, Dict[str, Any]] = {}
        
        # Default Italian voice models configuration
        self.default_voice_configs = {
            "it-riccardo-x-low": {
                "name": "Riccardo (Italian Male)",
                "language": VoiceLanguage.ITALIAN,
                "gender": VoiceGender.MALE,
                "quality": "low",
                "description": "Natural sounding Italian male voice"
            },
            "it-paola-medium": {
                "name": "Paola (Italian Female)",
                "language": VoiceLanguage.ITALIAN,
                "gender": VoiceGender.FEMALE,
                "quality": "medium",
                "description": "Clear Italian female voice"
            },
            "it-giuseppe-high": {
                "name": "Giuseppe (Italian Male HQ)",
                "language": VoiceLanguage.ITALIAN,
                "gender": VoiceGender.MALE,
                "quality": "high",
                "description": "High quality Italian male voice"
            },
            "en-us-amy-low": {
                "name": "Amy (English Female)",
                "language": VoiceLanguage.ENGLISH,
                "gender": VoiceGender.FEMALE,
                "quality": "low",
                "description": "English fallback voice"
            }
        }
        
        # Performance metrics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_audio_generated': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'voices_loaded': 0,
            'streaming_requests': 0,
            'errors': 0,
            'last_error': None,
        }
        
        logger.info(f"PiperTTSService initialized: models_dir={models_dir}")
    
    async def initialize(self) -> None:
        """Initialize TTS service and load voice models."""
        try:
            logger.info("Initializing Piper TTS service...")
            
            # Discover available voice models
            await self._discover_voice_models()
            
            # Load default voice
            await self._load_voice(self.default_voice)
            
            # Cleanup old cache entries
            await self._cleanup_cache()
            
            logger.success(f"PiperTTSService initialized with {len(self.available_voices)} voices")
            
        except Exception as e:
            logger.error(f"Failed to initialize PiperTTSService: {e}")
            raise
    
    async def _discover_voice_models(self) -> None:
        """Discover and register available voice models."""
        
        # Register default voice configurations
        for voice_id, config in self.default_voice_configs.items():
            model_path = self.models_dir / f"{voice_id}.onnx"
            config_path = self.models_dir / f"{voice_id}.onnx.json"
            
            voice_model = VoiceModel(
                id=voice_id,
                name=config["name"],
                language=config["language"],
                gender=config["gender"],
                model_path=model_path,
                config_path=config_path if config_path.exists() else None,
                quality=config["quality"],
                description=config["description"],
                is_available=model_path.exists()
            )
            
            self.available_voices[voice_id] = voice_model
            
            if voice_model.is_available:
                logger.info(f"Found voice model: {voice_id} ({voice_model.name})")
            else:
                logger.warning(f"Voice model not found: {voice_id} at {model_path}")
        
        # Scan for additional models in directory
        if self.models_dir.exists():
            for model_file in self.models_dir.glob("*.onnx"):
                voice_id = model_file.stem
                if voice_id not in self.available_voices:
                    # Create generic voice model entry
                    self.available_voices[voice_id] = VoiceModel(
                        id=voice_id,
                        name=voice_id.replace("-", " ").title(),
                        language=VoiceLanguage.ITALIAN,  # Default assumption
                        gender=VoiceGender.NEUTRAL,
                        model_path=model_file,
                        is_available=True,
                        description="Discovered voice model"
                    )
                    logger.info(f"Discovered additional voice: {voice_id}")
    
    async def _load_voice(self, voice_id: str) -> bool:
        """Load a voice model for synthesis.
        
        Args:
            voice_id: Voice identifier to load
            
        Returns:
            True if voice loaded successfully
        """
        if voice_id in self.loaded_voices:
            return True
        
        if voice_id not in self.available_voices:
            logger.error(f"Voice {voice_id} not available")
            return False
        
        voice_model = self.available_voices[voice_id]
        
        if not voice_model.is_available:
            logger.error(f"Voice model file not found: {voice_model.model_path}")
            return False
        
        try:
            if PIPER_AVAILABLE:
                # Load Piper voice model
                voice = piper.PiperVoice.load(
                    str(voice_model.model_path),
                    config_path=str(voice_model.config_path) if voice_model.config_path else None,
                    use_cuda=False  # CPU inference for compatibility
                )
                self.loaded_voices[voice_id] = voice
                self.stats['voices_loaded'] += 1
                logger.success(f"Loaded voice: {voice_id}")
                return True
            else:
                # Fallback: simulate loaded voice
                self.loaded_voices[voice_id] = {"fallback": True, "model": voice_model}
                logger.warning(f"Using fallback for voice: {voice_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load voice {voice_id}: {e}")
            return False
    
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech from text.
        
        Args:
            request: TTS synthesis request
            
        Returns:
            TTS response with audio data
        """
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(request)
            
            if self.enable_caching and request.cache_enabled:
                cached_response = await self._get_cached_audio(cache_key)
                if cached_response:
                    self.stats['cache_hits'] += 1
                    self.stats['successful_requests'] += 1
                    cached_response.cached = True
                    return cached_response
                else:
                    self.stats['cache_misses'] += 1
            
            # Ensure voice is loaded
            await self._ensure_voice_loaded(request.voice_id)
            
            # Preprocess text
            processed_text = await self._preprocess_text(request.text, request.ssml_settings)
            
            # Generate audio
            if request.streaming:
                # For streaming, we'll generate the full audio first (Piper doesn't support streaming)
                audio_data, sample_rate = await self._generate_audio(
                    processed_text, request.voice_id, request.prosody
                )
            else:
                audio_data, sample_rate = await self._generate_audio(
                    processed_text, request.voice_id, request.prosody
                )
            
            # Post-process audio
            audio_data = await self._postprocess_audio(
                audio_data, sample_rate, request.audio_format, request.prosody
            )
            
            # Calculate duration
            duration = len(audio_data) / (sample_rate * 2)  # Assuming 16-bit audio
            
            # Create response
            response = TTSResponse(
                audio_data=audio_data,
                sample_rate=sample_rate,
                duration=duration,
                format=request.audio_format,
                processing_time=time.time() - start_time,
                voice_id=request.voice_id,
                metadata={
                    'text_length': len(request.text),
                    'processed_text_length': len(processed_text),
                    'prosody_applied': request.prosody != ProsodySettings(),
                    'ssml_processed': request.ssml_settings.enable_ssml
                }
            )
            
            # Cache the response
            if self.enable_caching and request.cache_enabled:
                await self._cache_audio(cache_key, response)
            
            self.stats['successful_requests'] += 1
            self.stats['total_audio_generated'] += duration
            processing_time = time.time() - start_time
            self._update_processing_stats(processing_time)
            
            logger.debug(f"Synthesized {duration:.2f}s of audio in {processing_time:.3f}s")
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats['failed_requests'] += 1
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"TTS synthesis failed after {processing_time:.3f}s: {e}")
            raise
    
    async def synthesize_stream(self, request: TTSRequest) -> AsyncGenerator[bytes, None]:
        """Synthesize speech with streaming output.
        
        Args:
            request: TTS synthesis request
            
        Yields:
            Audio data chunks
        """
        try:
            # For Piper, we generate full audio then stream it in chunks
            response = await self.synthesize(request)
            
            # Stream audio in chunks
            chunk_size = 4096  # 4KB chunks
            audio_data = response.audio_data
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                yield chunk
                
                # Small delay to simulate streaming
                await asyncio.sleep(0.01)
            
            self.stats['streaming_requests'] += 1
            
        except Exception as e:
            logger.error(f"Streaming synthesis failed: {e}")
            raise
    
    async def _ensure_voice_loaded(self, voice_id: str) -> str:
        """Ensure a voice is loaded, with fallback logic.
        
        Args:
            voice_id: Requested voice ID
            
        Returns:
            Actually loaded voice ID
        """
        # Try to load requested voice
        if await self._load_voice(voice_id):
            return voice_id
        
        # Try default voice
        if voice_id != self.default_voice:
            logger.warning(f"Voice {voice_id} unavailable, trying default: {self.default_voice}")
            if await self._load_voice(self.default_voice):
                return self.default_voice
        
        # Try fallback voice
        if voice_id != self.fallback_voice:
            logger.warning(f"Default voice unavailable, trying fallback: {self.fallback_voice}")
            if await self._load_voice(self.fallback_voice):
                return self.fallback_voice
        
        # Use any available voice
        for available_voice_id in self.available_voices:
            if self.available_voices[available_voice_id].is_available:
                logger.warning(f"Using available voice: {available_voice_id}")
                if await self._load_voice(available_voice_id):
                    return available_voice_id
        
        raise RuntimeError("No TTS voices available")
    
    async def _preprocess_text(self, text: str, ssml_settings: SSMLSettings) -> str:
        """Preprocess text for synthesis.
        
        Args:
            text: Input text
            ssml_settings: SSML processing settings
            
        Returns:
            Preprocessed text
        """
        processed = text
        
        if ssml_settings.enable_ssml:
            # Process basic SSML tags
            processed = await self._process_ssml(processed, ssml_settings)
        
        # Clean up text
        processed = processed.strip()
        
        return processed
    
    async def _process_ssml(self, text: str, settings: SSMLSettings) -> str:
        """Process SSML markup in text.
        
        Args:
            text: Text with SSML markup
            settings: SSML processing settings
            
        Returns:
            Processed text (SSML removed, effects noted)
        """
        import re
        
        processed = text
        
        if settings.enable_breaks:
            # Convert break tags to pauses
            processed = re.sub(r'<break\s+time="(\d+)ms"\s*/>', r'<pause:\1>', processed)
            processed = re.sub(r'<break\s+time="(\d+)s"\s*/>', lambda m: f'<pause:{int(m.group(1))*1000}>', processed)
            processed = re.sub(r'<break\s*/>', '<pause:500>', processed)
        
        if settings.enable_emphasis:
            # Mark emphasized text
            processed = re.sub(r'<emphasis[^>]*>(.*?)</emphasis>', r'<emph>\1</emph>', processed)
        
        if settings.enable_prosody:
            # Extract prosody information (simplified)
            processed = re.sub(r'<prosody[^>]*>(.*?)</prosody>', r'\1', processed)
        
        # Remove remaining SSML tags for Piper compatibility
        processed = re.sub(r'<[^>]+>', '', processed)
        
        return processed
    
    async def _generate_audio(self, text: str, voice_id: str, prosody: ProsodySettings) -> tuple[bytes, int]:
        """Generate audio from preprocessed text.
        
        Args:
            text: Preprocessed text
            voice_id: Voice to use
            prosody: Prosody settings
            
        Returns:
            Tuple of (audio_data, sample_rate)
        """
        if voice_id not in self.loaded_voices:
            raise ValueError(f"Voice {voice_id} not loaded")
        
        voice = self.loaded_voices[voice_id]
        
        if PIPER_AVAILABLE and not isinstance(voice, dict):
            # Use actual Piper synthesis
            audio_data = voice.synthesize(text)
            
            # Convert to bytes
            audio_bytes = audio_data.tobytes()
            sample_rate = voice.config.sample_rate
            
        else:
            # Fallback synthesis (generate silence or use system TTS)
            duration = max(len(text) * 0.1, 1.0)  # Estimate duration
            sample_rate = 22050
            samples = int(duration * sample_rate)
            
            # Generate simple tone or silence as fallback
            audio_array = np.zeros(samples, dtype=np.float32)
            audio_bytes = (audio_array * 32767).astype(np.int16).tobytes()
            
            logger.warning(f"Using fallback audio generation for: {text[:50]}...")
        
        return audio_bytes, sample_rate
    
    async def _postprocess_audio(self,
                                audio_data: bytes,
                                sample_rate: int,
                                output_format: AudioFormat,
                                prosody: ProsodySettings) -> bytes:
        """Post-process generated audio.
        
        Args:
            audio_data: Raw audio data
            sample_rate: Audio sample rate
            output_format: Desired output format
            prosody: Prosody settings to apply
            
        Returns:
            Processed audio data
        """
        if not AUDIO_PROCESSING_AVAILABLE:
            return audio_data
        
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
            
            # Apply prosody modifications
            if prosody.speed != 1.0:
                # Change playback speed
                audio_array = librosa.effects.time_stretch(audio_array, rate=prosody.speed)
            
            if prosody.pitch != 1.0:
                # Change pitch
                audio_array = librosa.effects.pitch_shift(
                    audio_array, sr=sample_rate, n_steps=12 * np.log2(prosody.pitch)
                )
            
            if prosody.volume != 1.0:
                # Adjust volume
                audio_array = audio_array * prosody.volume
                audio_array = np.clip(audio_array, -1.0, 1.0)  # Prevent clipping
            
            # Convert back to int16
            processed_audio = (audio_array * 32767).astype(np.int16)
            
            # Format conversion if needed
            if output_format != AudioFormat.WAV:
                processed_audio = await self._convert_audio_format(
                    processed_audio, sample_rate, output_format
                )
            else:
                processed_audio = processed_audio.tobytes()
            
            return processed_audio
            
        except Exception as e:
            logger.error(f"Audio post-processing failed: {e}")
            return audio_data
    
    async def _convert_audio_format(self,
                                  audio_array: np.ndarray,
                                  sample_rate: int,
                                  format: AudioFormat) -> bytes:
        """Convert audio to different format.
        
        Args:
            audio_array: Audio data array
            sample_rate: Sample rate
            format: Target format
            
        Returns:
            Converted audio bytes
        """
        try:
            with tempfile.NamedTemporaryFile(suffix=f".{format.value}", delete=False) as temp_file:
                if format == AudioFormat.WAV:
                    # Write WAV file
                    sf.write(temp_file.name, audio_array, sample_rate)
                elif format == AudioFormat.MP3:
                    # Convert to MP3 using ffmpeg
                    wav_file = temp_file.name.replace('.mp3', '.wav')
                    sf.write(wav_file, audio_array, sample_rate)
                    
                    subprocess.run([
                        'ffmpeg', '-i', wav_file, '-codec:a', 'libmp3lame', 
                        '-b:a', '128k', temp_file.name, '-y'
                    ], check=True, capture_output=True)
                    
                    os.unlink(wav_file)
                
                # Read converted file
                with open(temp_file.name, 'rb') as f:
                    converted_data = f.read()
                
                os.unlink(temp_file.name)
                return converted_data
                
        except Exception as e:
            logger.error(f"Format conversion failed: {e}")
            return audio_array.tobytes()
    
    def _generate_cache_key(self, request: TTSRequest) -> str:
        """Generate cache key for TTS request."""
        key_data = {
            'text': request.text,
            'voice_id': request.voice_id,
            'prosody': {
                'speed': request.prosody.speed,
                'pitch': request.prosody.pitch,
                'volume': request.prosody.volume,
            },
            'format': request.audio_format.value,
            'quality': request.quality
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def _get_cached_audio(self, cache_key: str) -> Optional[TTSResponse]:
        """Retrieve cached audio response."""
        if cache_key not in self.audio_cache:
            return None
        
        cached_entry = self.audio_cache[cache_key]
        
        # Check if cache entry is still valid
        if datetime.now() - cached_entry['timestamp'] > timedelta(seconds=self.cache_ttl):
            del self.audio_cache[cache_key]
            return None
        
        return cached_entry['response']
    
    async def _cache_audio(self, cache_key: str, response: TTSResponse) -> None:
        """Cache audio response."""
        # Limit cache size
        if len(self.audio_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = min(self.audio_cache.keys(), 
                           key=lambda k: self.audio_cache[k]['timestamp'])
            del self.audio_cache[oldest_key]
        
        self.audio_cache[cache_key] = {
            'response': response,
            'timestamp': datetime.now()
        }
    
    async def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        current_time = datetime.now()
        expired_keys = []
        
        for cache_key, entry in self.audio_cache.items():
            if current_time - entry['timestamp'] > timedelta(seconds=self.cache_ttl):
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            del self.audio_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _update_processing_stats(self, processing_time: float) -> None:
        """Update processing time statistics."""
        self.stats['total_processing_time'] += processing_time
        self.stats['average_processing_time'] = (
            self.stats['total_processing_time'] / self.stats['successful_requests']
        )
    
    def get_available_voices(self, language: Optional[VoiceLanguage] = None) -> List[VoiceModel]:
        """Get list of available voices."""
        voices = list(self.available_voices.values())
        
        if language:
            voices = [v for v in voices if v.language == language]
        
        return [v for v in voices if v.is_available]
    
    def get_voice_info(self, voice_id: str) -> Optional[VoiceModel]:
        """Get information about a specific voice."""
        return self.available_voices.get(voice_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on TTS service."""
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'piper_available': PIPER_AVAILABLE,
            'audio_processing_available': AUDIO_PROCESSING_AVAILABLE,
            'voices_available': len([v for v in self.available_voices.values() if v.is_available]),
            'voices_loaded': len(self.loaded_voices),
            'cache_entries': len(self.audio_cache),
            'errors': []
        }
        
        try:
            # Test synthesis with default voice
            test_request = TTSRequest(
                text="Test synthesis",
                voice_id=self.default_voice,
                cache_enabled=False
            )
            
            start_time = time.time()
            await self.synthesize(test_request)
            test_time = time.time() - start_time
            
            health['test_synthesis_time'] = test_time
            health['test_synthesis_success'] = True
            
        except Exception as e:
            health['status'] = 'degraded'
            health['test_synthesis_success'] = False
            health['errors'].append(f'Test synthesis failed: {str(e)}')
        
        if self.stats['errors'] > 0:
            health['recent_errors'] = self.stats['errors']
            health['last_error'] = self.stats['last_error']
        
        return health
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = self.stats.copy()
        
        if stats['total_requests'] > 0:
            stats['success_rate'] = (stats['successful_requests'] / stats['total_requests']) * 100
            stats['cache_hit_rate'] = (stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses'])) * 100 if (stats['cache_hits'] + stats['cache_misses']) > 0 else 0
            stats['error_rate'] = (stats['failed_requests'] / stats['total_requests']) * 100
        
        stats.update({
            'voices': {
                'available': len([v for v in self.available_voices.values() if v.is_available]),
                'loaded': len(self.loaded_voices),
                'total_configured': len(self.available_voices),
            },
            'cache': {
                'entries': len(self.audio_cache),
                'max_size': self.max_cache_size,
                'enabled': self.enable_caching,
            },
            'configuration': {
                'models_dir': str(self.models_dir),
                'cache_dir': str(self.cache_dir),
                'default_voice': self.default_voice,
                'fallback_voice': self.fallback_voice,
            }
        })
        
        return stats
    
    async def clear_cache(self) -> int:
        """Clear audio cache and return number of entries cleared."""
        cleared = len(self.audio_cache)
        self.audio_cache.clear()
        logger.info(f"Cleared {cleared} TTS cache entries")
        return cleared