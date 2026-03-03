"""TTS Manager for coordinating all Text-to-Speech components and operations."""

import asyncio
import time
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, AsyncGenerator, Any, Union
from datetime import datetime
from pathlib import Path

from loguru import logger

from .piper_service import PiperTTSService, TTSRequest, TTSResponse, AudioFormat, VoiceGender, VoiceLanguage
from .tts_processor import TTSProcessor, ProcessingSettings, EmotionType, ProcessedText
from .audio_stream import AudioResponseStream, StreamingConfig, StreamChunk, StreamingFormat
from .voice_personalizer import VoicePersonalizer, PersonalizationProfile, PersonalityType
from voicehelpdeskai.services.nlu import IntentPrediction
from voicehelpdeskai.config.manager import get_config_manager


@dataclass
class TTSManagerConfig:
    """Configuration for TTS Manager."""
    models_dir: str = "./models/piper"
    cache_dir: str = "./cache/tts"
    enable_caching: bool = True
    enable_streaming: bool = True
    enable_personalization: bool = True
    enable_advanced_processing: bool = True
    default_voice_id: str = "it-riccardo-x-low"
    fallback_voice_id: str = "en-us-amy-low"
    quality_level: str = "medium"  # low, medium, high
    max_text_length: int = 1000


@dataclass
class SynthesisRequest:
    """Complete TTS synthesis request."""
    text: str
    user_id: Optional[str] = None
    voice_id: Optional[str] = None
    audio_format: AudioFormat = AudioFormat.WAV
    streaming: bool = False
    enable_personalization: bool = True
    enable_processing: bool = True
    target_emotion: Optional[EmotionType] = None
    intent: Optional[IntentPrediction] = None
    conversation_context: Optional[Dict[str, Any]] = None
    quality: str = "medium"
    metadata: Dict[str, Any] = None


@dataclass
class SynthesisResponse:
    """Complete TTS synthesis response."""
    audio_data: Optional[bytes] = None
    audio_stream: Optional[AsyncGenerator[StreamChunk, None]] = None
    sample_rate: int = 22050
    duration: float = 0.0
    format: AudioFormat = AudioFormat.WAV
    voice_id: str = ""
    processing_time: float = 0.0
    cached: bool = False
    personalization_applied: bool = False
    processing_applied: bool = False
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = None


class TTSManager:
    """Centralized manager for all TTS services and coordination."""
    
    def __init__(self, config: Optional[TTSManagerConfig] = None):
        """Initialize TTS Manager.
        
        Args:
            config: TTS manager configuration
        """
        self.app_config = get_config_manager().get_config()
        self.config = config or TTSManagerConfig()
        
        # Core services
        self.piper_service: Optional[PiperTTSService] = None
        self.tts_processor: Optional[TTSProcessor] = None
        self.voice_personalizer: Optional[VoicePersonalizer] = None
        
        # Service state
        self.is_initialized = False
        self.initialization_lock = threading.Lock()
        
        # Performance tracking
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'streaming_requests': 0,
            'personalized_requests': 0,
            'processed_requests': 0,
            'cached_responses': 0,
            'total_synthesis_time': 0.0,
            'total_audio_generated': 0.0,
            'average_synthesis_time': 0.0,
            'average_audio_duration': 0.0,
            'errors': 0,
            'last_error': None,
        }
        
        logger.info("TTS Manager initialized")
    
    async def initialize(self) -> None:
        """Initialize all TTS services."""
        if self.is_initialized:
            logger.warning("TTS Manager already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing TTS services...")
                
                # Initialize Piper TTS service
                self.piper_service = PiperTTSService(
                    models_dir=self.config.models_dir,
                    cache_dir=self.config.cache_dir,
                    enable_caching=self.config.enable_caching,
                    default_voice=self.config.default_voice_id,
                    fallback_voice=self.config.fallback_voice_id
                )
                await self.piper_service.initialize()
                logger.success("Piper TTS service initialized")
                
                # Initialize TTS processor
                if self.config.enable_advanced_processing:
                    self.tts_processor = TTSProcessor(
                        enable_advanced_processing=True,
                        enable_emotion_detection=True
                    )
                    logger.success("TTS processor initialized")
                
                # Initialize voice personalizer
                if self.config.enable_personalization:
                    self.voice_personalizer = VoicePersonalizer(
                        enable_user_learning=True,
                        enable_context_adaptation=True,
                        enable_cultural_adaptation=True
                    )
                    logger.success("Voice personalizer initialized")
                
                self.is_initialized = True
                logger.success("TTS Manager initialization complete")
                
            except Exception as e:
                logger.error(f"TTS Manager initialization failed: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                raise
    
    async def synthesize_speech(self, request: SynthesisRequest) -> SynthesisResponse:
        """Synthesize speech from text with full pipeline processing.
        
        Args:
            request: Complete synthesis request
            
        Returns:
            Synthesis response with audio data or stream
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        try:
            # Validate request
            await self._validate_request(request)
            
            # Step 1: Text preprocessing
            processed_text = None
            if request.enable_processing and self.tts_processor:
                processing_settings = ProcessingSettings()
                processed_text = await self.tts_processor.process_text(
                    request.text,
                    settings=processing_settings,
                    target_emotion=request.target_emotion
                )
                text_for_synthesis = processed_text.processed_text
                self.stats['processed_requests'] += 1
            else:
                text_for_synthesis = request.text
            
            # Step 2: Voice personalization
            personalization_profile = None
            if request.enable_personalization and self.voice_personalizer:
                personalization_profile = await self.voice_personalizer.personalize_voice(
                    text=text_for_synthesis,
                    user_id=request.user_id,
                    intent=request.intent,
                    conversation_context=request.conversation_context,
                    target_emotion=request.target_emotion
                )
                self.stats['personalized_requests'] += 1
            
            # Step 3: Prepare TTS request
            tts_request = await self._create_tts_request(
                request, text_for_synthesis, processed_text, personalization_profile
            )
            
            # Step 4: Generate audio
            if request.streaming:
                # Streaming synthesis
                audio_stream = await self._synthesize_streaming(tts_request, request)
                synthesis_response = SynthesisResponse(
                    audio_stream=audio_stream,
                    format=request.audio_format,
                    voice_id=tts_request.voice_id,
                    processing_time=time.time() - start_time,
                    personalization_applied=personalization_profile is not None,
                    processing_applied=processed_text is not None,
                    confidence_score=personalization_profile.confidence_score if personalization_profile else 0.5,
                    metadata=self._create_response_metadata(request, processed_text, personalization_profile)
                )
                self.stats['streaming_requests'] += 1
            else:
                # Standard synthesis
                tts_response = await self.piper_service.synthesize(tts_request)
                synthesis_response = SynthesisResponse(
                    audio_data=tts_response.audio_data,
                    sample_rate=tts_response.sample_rate,
                    duration=tts_response.duration,
                    format=tts_response.format,
                    voice_id=tts_response.voice_id,
                    processing_time=time.time() - start_time,
                    cached=tts_response.cached,
                    personalization_applied=personalization_profile is not None,
                    processing_applied=processed_text is not None,
                    confidence_score=personalization_profile.confidence_score if personalization_profile else 0.5,
                    metadata=self._create_response_metadata(request, processed_text, personalization_profile)
                )
                
                if tts_response.cached:
                    self.stats['cached_responses'] += 1
            
            # Update statistics
            self._update_synthesis_stats(synthesis_response)
            self.stats['successful_requests'] += 1
            
            logger.debug(f"Synthesized speech in {synthesis_response.processing_time:.3f}s: "
                        f"duration={synthesis_response.duration:.2f}s, voice={synthesis_response.voice_id}")
            
            return synthesis_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats['failed_requests'] += 1
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"Speech synthesis failed after {processing_time:.3f}s: {e}")
            
            # Return error response
            return SynthesisResponse(
                processing_time=processing_time,
                metadata={'error': str(e)}
            )
    
    async def _validate_request(self, request: SynthesisRequest) -> None:
        """Validate synthesis request."""
        if not request.text or not request.text.strip():
            raise ValueError("Text cannot be empty")
        
        if len(request.text) > self.config.max_text_length:
            raise ValueError(f"Text too long: {len(request.text)} > {self.config.max_text_length}")
        
        if request.voice_id and request.voice_id not in self.piper_service.available_voices:
            logger.warning(f"Requested voice {request.voice_id} not available, using default")
            request.voice_id = None
    
    async def _create_tts_request(self,
                                request: SynthesisRequest,
                                processed_text: str,
                                text_processing: Optional[ProcessedText],
                                personalization: Optional[PersonalizationProfile]) -> TTSRequest:
        """Create TTS request from synthesis request."""
        
        # Determine voice ID
        voice_id = request.voice_id or self.config.default_voice_id
        
        # Apply personalization if available
        prosody_settings = None
        if personalization:
            prosody_settings = personalization.base_prosody
            
            # Apply context adaptations
            if personalization.context_adaptations:
                prosody_settings.speed *= personalization.context_adaptations.speed_modifier
                prosody_settings.pitch *= personalization.context_adaptations.pitch_modifier
                prosody_settings.volume *= personalization.context_adaptations.volume_modifier
        
        # Create TTS request
        tts_request = TTSRequest(
            text=processed_text,
            voice_id=voice_id,
            prosody=prosody_settings,
            audio_format=request.audio_format,
            streaming=request.streaming,
            quality=request.quality,
            metadata=request.metadata or {}
        )
        
        return tts_request
    
    async def _synthesize_streaming(self,
                                  tts_request: TTSRequest,
                                  original_request: SynthesisRequest) -> AsyncGenerator[StreamChunk, None]:
        """Create streaming synthesis."""
        
        # Generate full audio first (Piper doesn't support true streaming)
        tts_response = await self.piper_service.synthesize(tts_request)
        
        # Create streaming configuration
        streaming_config = StreamingConfig(
            format=StreamingFormat.WAV_CHUNKS if original_request.audio_format == AudioFormat.WAV else StreamingFormat.RAW_PCM,
            sample_rate=tts_response.sample_rate,
            enable_compression=True,
            enable_silence_detection=True
        )
        
        # Create audio stream
        audio_stream = AudioResponseStream(
            config=streaming_config,
            enable_real_time=True,
            enable_adaptive_quality=True
        )
        
        # Start streaming
        await audio_stream.start_stream(tts_response.audio_data)
        
        # Stream chunks
        async for chunk in audio_stream.stream_chunks():
            yield chunk
    
    def _create_response_metadata(self,
                                request: SynthesisRequest,
                                text_processing: Optional[ProcessedText],
                                personalization: Optional[PersonalizationProfile]) -> Dict[str, Any]:
        """Create response metadata."""
        
        metadata = {
            'original_text_length': len(request.text),
            'synthesis_timestamp': datetime.now().isoformat(),
            'quality_level': request.quality,
        }
        
        if text_processing:
            metadata.update({
                'text_processing': {
                    'processed_text_length': len(text_processing.processed_text),
                    'emotion_detected': text_processing.emotion_settings.primary_emotion.value,
                    'pause_locations_count': len(text_processing.pause_locations),
                    'emphasis_regions_count': len(text_processing.emphasis_regions),
                    'processing_time': text_processing.processing_time,
                }
            })
        
        if personalization:
            metadata.update({
                'personalization': {
                    'personality': personalization.personality.value,
                    'cultural_style': personalization.cultural_style.value,
                    'speech_style': personalization.speech_style.value,
                    'confidence_score': personalization.confidence_score,
                    'user_id': request.user_id,
                }
            })
        
        return metadata
    
    def _update_synthesis_stats(self, response: SynthesisResponse) -> None:
        """Update synthesis statistics."""
        self.stats['total_synthesis_time'] += response.processing_time
        
        if response.duration > 0:
            self.stats['total_audio_generated'] += response.duration
        
        # Update averages
        if self.stats['successful_requests'] > 0:
            self.stats['average_synthesis_time'] = (
                self.stats['total_synthesis_time'] / self.stats['successful_requests']
            )
        
        if self.stats['total_audio_generated'] > 0:
            self.stats['average_audio_duration'] = (
                self.stats['total_audio_generated'] / self.stats['successful_requests']
            )
    
    async def get_available_voices(self, language: Optional[VoiceLanguage] = None) -> List[Dict[str, Any]]:
        """Get list of available voices.
        
        Args:
            language: Optional language filter
            
        Returns:
            List of voice information
        """
        if not self.piper_service:
            return []
        
        voices = self.piper_service.get_available_voices(language)
        
        return [{
            'id': voice.id,
            'name': voice.name,
            'language': voice.language.value,
            'gender': voice.gender.value,
            'quality': voice.quality,
            'description': voice.description,
            'is_available': voice.is_available
        } for voice in voices]
    
    async def record_user_feedback(self,
                                 user_id: str,
                                 satisfaction_score: float,
                                 feedback_details: Optional[Dict[str, Any]] = None) -> None:
        """Record user feedback for voice personalization.
        
        Args:
            user_id: User identifier
            satisfaction_score: Satisfaction score (1.0-5.0)
            feedback_details: Optional detailed feedback
        """
        if self.voice_personalizer:
            await self.voice_personalizer.record_user_feedback(
                user_id, satisfaction_score, feedback_details
            )
    
    async def update_user_voice_preferences(self,
                                          user_id: str,
                                          preferences: Dict[str, Any]) -> None:
        """Update user voice preferences.
        
        Args:
            user_id: User identifier
            preferences: Voice preferences to update
        """
        if self.voice_personalizer:
            await self.voice_personalizer.update_user_preferences(user_id, preferences)
    
    async def get_user_voice_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user voice preferences.
        
        Args:
            user_id: User identifier
            
        Returns:
            User preferences or None
        """
        if not self.voice_personalizer:
            return None
        
        prefs = self.voice_personalizer.get_user_preferences(user_id)
        if not prefs:
            return None
        
        return {
            'preferred_gender': prefs.preferred_gender.value if prefs.preferred_gender else None,
            'preferred_speed': prefs.preferred_speed,
            'preferred_pitch': prefs.preferred_pitch,
            'preferred_volume': prefs.preferred_volume,
            'preferred_personality': prefs.preferred_personality.value,
            'cultural_style': prefs.cultural_style.value,
            'interaction_count': len(prefs.interaction_history),
            'average_feedback': sum(prefs.feedback_scores) / len(prefs.feedback_scores) if prefs.feedback_scores else None,
            'last_updated': prefs.last_updated.isoformat()
        }
    
    async def batch_synthesize(self, requests: List[SynthesisRequest]) -> List[SynthesisResponse]:
        """Synthesize multiple texts in batch.
        
        Args:
            requests: List of synthesis requests
            
        Returns:
            List of synthesis responses
        """
        tasks = [self.synthesize_speech(request) for request in requests]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Batch synthesis failed for request {i}: {response}")
                results.append(SynthesisResponse(
                    metadata={'batch_error': str(response)}
                ))
            else:
                results.append(response)
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all TTS services."""
        health = {
            'overall_status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {},
            'errors': []
        }
        
        try:
            # Check initialization
            if not self.is_initialized:
                health['services']['initialization'] = 'not_initialized'
                health['overall_status'] = 'unhealthy'
                health['errors'].append('Manager not initialized')
            else:
                health['services']['initialization'] = 'healthy'
            
            # Check Piper service
            if self.piper_service:
                piper_health = await self.piper_service.health_check()
                health['services']['piper_service'] = piper_health['status']
                if piper_health['status'] != 'healthy':
                    health['overall_status'] = 'degraded'
                    health['errors'].extend(piper_health.get('errors', []))
            else:
                health['services']['piper_service'] = 'disabled'
            
            # Check processor
            if self.config.enable_advanced_processing:
                if self.tts_processor:
                    health['services']['tts_processor'] = 'healthy'
                else:
                    health['services']['tts_processor'] = 'unhealthy'
                    health['errors'].append('TTS processor not initialized')
                    health['overall_status'] = 'degraded'
            else:
                health['services']['tts_processor'] = 'disabled'
            
            # Check personalizer
            if self.config.enable_personalization:
                if self.voice_personalizer:
                    health['services']['voice_personalizer'] = 'healthy'
                else:
                    health['services']['voice_personalizer'] = 'unhealthy'
                    health['errors'].append('Voice personalizer not initialized')
                    health['overall_status'] = 'degraded'
            else:
                health['services']['voice_personalizer'] = 'disabled'
            
            # Add error statistics
            if self.stats['errors'] > 0:
                health['recent_errors'] = self.stats['errors']
                health['last_error'] = self.stats['last_error']
                if self.stats['failed_requests'] / max(self.stats['total_requests'], 1) > 0.1:
                    health['overall_status'] = 'degraded'
            
        except Exception as e:
            health['overall_status'] = 'unhealthy'
            health['errors'].append(f'Health check failed: {str(e)}')
        
        return health
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all services."""
        stats = self.stats.copy()
        
        # Add service-specific statistics
        if self.piper_service:
            stats['piper_service'] = self.piper_service.get_stats()
        
        if self.tts_processor:
            stats['tts_processor'] = self.tts_processor.get_stats()
        
        if self.voice_personalizer:
            stats['voice_personalizer'] = self.voice_personalizer.get_stats()
        
        # Add configuration info
        stats['configuration'] = {
            'models_dir': self.config.models_dir,
            'cache_dir': self.config.cache_dir,
            'default_voice_id': self.config.default_voice_id,
            'fallback_voice_id': self.config.fallback_voice_id,
            'quality_level': self.config.quality_level,
            'max_text_length': self.config.max_text_length,
            'features_enabled': {
                'caching': self.config.enable_caching,
                'streaming': self.config.enable_streaming,
                'personalization': self.config.enable_personalization,
                'advanced_processing': self.config.enable_advanced_processing,
            }
        }
        
        # Add derived metrics
        if stats['total_requests'] > 0:
            stats['success_rate'] = (stats['successful_requests'] / stats['total_requests']) * 100
            stats['streaming_rate'] = (stats['streaming_requests'] / stats['total_requests']) * 100
            stats['personalization_rate'] = (stats['personalized_requests'] / stats['total_requests']) * 100
            stats['processing_rate'] = (stats['processed_requests'] / stats['total_requests']) * 100
            stats['cache_hit_rate'] = (stats['cached_responses'] / stats['total_requests']) * 100
        
        return stats
    
    async def clear_all_caches(self) -> Dict[str, int]:
        """Clear all caches and return cleanup statistics."""
        cleanup_stats = {'total_cleared': 0}
        
        try:
            # Clear Piper service cache
            if self.piper_service:
                cleared = await self.piper_service.clear_cache()
                cleanup_stats['piper_cache'] = cleared
                cleanup_stats['total_cleared'] += cleared
            
            logger.info(f"Cleared {cleanup_stats['total_cleared']} TTS cache entries")
            
        except Exception as e:
            logger.error(f"TTS cache cleanup failed: {e}")
            cleanup_stats['error'] = str(e)
        
        return cleanup_stats
    
    async def shutdown(self) -> None:
        """Shutdown all TTS services."""
        try:
            logger.info("Shutting down TTS Manager...")
            
            # Reset state
            self.is_initialized = False
            self.piper_service = None
            self.tts_processor = None
            self.voice_personalizer = None
            
            logger.success("TTS Manager shutdown complete")
            
        except Exception as e:
            logger.error(f"TTS Manager shutdown failed: {e}")


# Global TTS manager instance
_tts_manager: Optional[TTSManager] = None


def get_tts_manager() -> TTSManager:
    """Get global TTS manager instance."""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSManager()
    return _tts_manager