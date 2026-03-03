"""STT Service Manager for coordinating all transcription components."""

import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator, Any, Union
from pathlib import Path
import threading
from datetime import datetime

import numpy as np
from loguru import logger

from .whisper_service import WhisperService, TranscriptionResult
from .transcription_processor import TranscriptionProcessor, ProcessedTranscription
from .continuous_stream import ContinuousTranscriptionStream, StreamingTranscription, TranscriptionState
from .transcription_cache import TranscriptionCache
from voicehelpdeskai.config.manager import get_config_manager


class STTManager:
    """Centralized manager for all STT services and coordination."""
    
    def __init__(self,
                 whisper_model_size: str = "medium",
                 device: str = "auto",
                 enable_cache: bool = True,
                 enable_processing: bool = True,
                 enable_streaming: bool = True,
                 default_language: str = "it"):
        """Initialize STT Manager.
        
        Args:
            whisper_model_size: Size of Whisper model to use
            device: Device for inference (auto, cpu, cuda)
            enable_cache: Enable transcription caching
            enable_processing: Enable post-processing
            enable_streaming: Enable streaming capabilities
            default_language: Default language for transcription
        """
        self.config = get_config_manager().get_config()
        self.whisper_model_size = whisper_model_size
        self.device = device
        self.enable_cache = enable_cache
        self.enable_processing = enable_processing
        self.enable_streaming = enable_streaming
        self.default_language = default_language
        
        # Core services
        self.whisper_service: Optional[WhisperService] = None
        self.processor: Optional[TranscriptionProcessor] = None
        self.cache: Optional[TranscriptionCache] = None
        self.streaming_service: Optional[ContinuousTranscriptionStream] = None
        
        # Service state
        self.is_initialized = False
        self.is_streaming_active = False
        self.initialization_lock = threading.Lock()
        
        # Performance tracking
        self.stats = {
            'total_transcriptions': 0,
            'cached_transcriptions': 0,
            'processed_transcriptions': 0,
            'streaming_sessions': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'cache_hit_rate': 0.0,
            'errors': 0,
            'last_error': None,
        }
        
        logger.info(f"STT Manager initialized with model: {whisper_model_size}, device: {device}")
    
    async def initialize(self) -> None:
        """Initialize all STT services."""
        if self.is_initialized:
            logger.warning("STT Manager already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing STT services...")
                
                # Initialize Whisper service
                self.whisper_service = WhisperService(
                    model_size=self.whisper_model_size,
                    device=self.device,
                    compute_type="auto",
                    num_workers=2
                )
                await self.whisper_service.load_model()
                logger.success("Whisper service initialized")
                
                # Initialize transcription processor
                if self.enable_processing:
                    self.processor = TranscriptionProcessor(
                        enable_punctuation=True,
                        enable_number_normalization=True,
                        enable_acronym_expansion=True,
                        enable_profanity_filter=True,
                        enable_ner=True,
                        enable_spell_correction=True
                    )
                    logger.success("Transcription processor initialized")
                
                # Initialize cache
                if self.enable_cache:
                    self.cache = TranscriptionCache(
                        ttl_seconds=self.config.redis.transcription_cache_ttl,
                        enable_compression=True,
                        enable_fuzzy_matching=True,
                        fuzzy_threshold=0.85,
                        max_memory_entries=1000
                    )
                    logger.success("Transcription cache initialized")
                
                # Initialize streaming service
                if self.enable_streaming:
                    self.streaming_service = ContinuousTranscriptionStream(
                        whisper_service=self.whisper_service,
                        transcription_processor=self.processor,
                        chunk_duration=1.0,
                        overlap_duration=0.2,
                        enable_vad=True,
                        enable_context_correction=True,
                        enable_interruption_detection=True,
                        language=self.default_language
                    )
                    logger.success("Continuous transcription stream initialized")
                
                # Warm up services
                await self._warmup_services()
                
                self.is_initialized = True
                logger.success("STT Manager initialization complete")
                
            except Exception as e:
                logger.error(f"STT Manager initialization failed: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                raise
    
    async def _warmup_services(self) -> None:
        """Warm up all services for better first-request performance."""
        try:
            if self.whisper_service:
                await self.whisper_service.warmup()
            
            logger.info("STT services warmed up")
            
        except Exception as e:
            logger.warning(f"Service warmup failed: {e}")
    
    async def transcribe(self,
                        audio_data: Union[np.ndarray, str, Path],
                        language: Optional[str] = None,
                        use_cache: bool = True,
                        enable_processing: bool = True,
                        sample_rate: int = 16000) -> ProcessedTranscription:
        """Transcribe audio with full processing pipeline.
        
        Args:
            audio_data: Audio data as numpy array or file path
            language: Target language (None for auto-detection)
            use_cache: Whether to use caching
            enable_processing: Whether to apply post-processing
            sample_rate: Audio sample rate if numpy array
            
        Returns:
            ProcessedTranscription with full metadata
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        language = language or self.default_language
        
        try:
            # Check cache first
            cached_result = None
            if use_cache and self.cache and isinstance(audio_data, np.ndarray):
                cache_result = await self.cache.get(audio_data, sample_rate, language)
                if cache_result:
                    transcription_result, processed_result = cache_result
                    if processed_result:
                        self.stats['cached_transcriptions'] += 1
                        self._update_stats(time.time() - start_time, cached=True)
                        logger.debug("Using cached transcription result")
                        return processed_result
                    cached_result = transcription_result
            
            # Perform transcription
            if cached_result:
                transcription_result = cached_result
            else:
                transcription_result = await self.whisper_service.transcribe_audio(
                    audio_data=audio_data,
                    language=language,
                    word_timestamps=True,
                    vad_filter=True,
                    temperature=0.0
                )
            
            # Apply post-processing
            if enable_processing and self.processor:
                processed_result = self.processor.process(transcription_result)
                self.stats['processed_transcriptions'] += 1
            else:
                processed_result = ProcessedTranscription(
                    text=transcription_result.text,
                    original_text=transcription_result.text,
                    confidence=transcription_result.confidence,
                    language=transcription_result.language,
                    processing_applied=[],
                    entities=[],
                    normalized_numbers=[],
                    corrected_words=[],
                    profanity_filtered=False,
                    processing_time=0.0
                )
            
            # Cache result
            if use_cache and self.cache and isinstance(audio_data, np.ndarray):
                await self.cache.put(
                    audio_data=audio_data,
                    transcription_result=transcription_result,
                    processed_result=processed_result,
                    sample_rate=sample_rate,
                    model_version=self.whisper_model_size,
                    processing_version="1.0.0"
                )
            
            processing_time = time.time() - start_time
            self._update_stats(processing_time, cached=False)
            
            logger.debug(f"Transcription completed in {processing_time:.2f}s: "
                        f"'{processed_result.text[:50]}{'...' if len(processed_result.text) > 50 else ''}'")
            
            return processed_result
            
        except Exception as e:
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            processing_time = time.time() - start_time
            self._update_stats(processing_time, error=True)
            logger.error(f"Transcription failed after {processing_time:.2f}s: {e}")
            raise
    
    async def transcribe_streaming(self,
                                  audio_chunks: AsyncGenerator[np.ndarray, None],
                                  language: Optional[str] = None,
                                  sample_rate: int = 16000) -> AsyncGenerator[StreamingTranscription, None]:
        """Transcribe streaming audio chunks.
        
        Args:
            audio_chunks: Async generator of audio chunks
            language: Target language
            sample_rate: Audio sample rate
            
        Yields:
            StreamingTranscription results
        """
        if not self.is_initialized:
            await self.initialize()
        
        if not self.streaming_service:
            raise RuntimeError("Streaming service not enabled")
        
        language = language or self.default_language
        
        try:
            await self.streaming_service.start_stream()
            await self.streaming_service.set_language(language)
            self.is_streaming_active = True
            self.stats['streaming_sessions'] += 1
            
            logger.info(f"Started streaming transcription session with language: {language}")
            
            async for chunk in audio_chunks:
                if not self.is_streaming_active:
                    break
                
                async for transcription in self.streaming_service.process_audio_chunk(
                    chunk, sample_rate
                ):
                    yield transcription
            
        except Exception as e:
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"Streaming transcription failed: {e}")
            raise
        finally:
            if self.streaming_service:
                await self.streaming_service.stop_stream()
            self.is_streaming_active = False
            logger.info("Streaming transcription session ended")
    
    async def detect_language(self, audio_data: Union[np.ndarray, str, Path]) -> tuple[str, float]:
        """Detect language from audio.
        
        Args:
            audio_data: Audio data
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if not self.is_initialized:
            await self.initialize()
        
        return await self.whisper_service.detect_language(audio_data)
    
    async def stop_streaming(self) -> None:
        """Stop active streaming session."""
        if self.is_streaming_active and self.streaming_service:
            await self.streaming_service.stop_stream()
            self.is_streaming_active = False
            logger.info("Streaming session stopped")
    
    def _update_stats(self, processing_time: float, cached: bool = False, error: bool = False) -> None:
        """Update performance statistics."""
        if not error:
            self.stats['total_transcriptions'] += 1
            self.stats['total_processing_time'] += processing_time
            self.stats['average_processing_time'] = (
                self.stats['total_processing_time'] / self.stats['total_transcriptions']
            )
            
            if cached:
                self.stats['cache_hit_rate'] = (
                    self.stats['cached_transcriptions'] / self.stats['total_transcriptions'] * 100
                )
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status."""
        status = {
            'initialized': self.is_initialized,
            'streaming_active': self.is_streaming_active,
            'services': {
                'whisper': self.whisper_service is not None,
                'processor': self.processor is not None,
                'cache': self.cache is not None,
                'streaming': self.streaming_service is not None,
            },
            'configuration': {
                'model_size': self.whisper_model_size,
                'device': self.device,
                'default_language': self.default_language,
                'cache_enabled': self.enable_cache,
                'processing_enabled': self.enable_processing,
                'streaming_enabled': self.enable_streaming,
            },
            'performance': self.stats.copy()
        }
        
        # Add service-specific stats
        if self.whisper_service:
            status['whisper_stats'] = self.whisper_service.get_stats()
        
        if self.processor:
            status['processor_stats'] = self.processor.get_processing_stats()
        
        if self.cache:
            status['cache_stats'] = self.cache.get_stats()
        
        if self.streaming_service:
            status['streaming_stats'] = self.streaming_service.get_performance_stats()
            status['streaming_context'] = await self.streaming_service.get_context_summary()
        
        return status
    
    async def cleanup_cache(self) -> Dict[str, int]:
        """Clean up expired cache entries.
        
        Returns:
            Dictionary with cleanup statistics
        """
        if not self.cache:
            return {'cleaned': 0, 'error': 'Cache not enabled'}
        
        try:
            cleaned_count = await self.cache.cleanup_expired()
            return {'cleaned': cleaned_count}
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return {'cleaned': 0, 'error': str(e)}
    
    async def invalidate_cache(self, model_version: Optional[str] = None) -> Dict[str, int]:
        """Invalidate cache entries.
        
        Args:
            model_version: Specific model version to invalidate (None for all)
            
        Returns:
            Dictionary with invalidation statistics
        """
        if not self.cache:
            return {'invalidated': 0, 'error': 'Cache not enabled'}
        
        try:
            if model_version:
                invalidated_count = await self.cache.invalidate_by_model_version(model_version)
            else:
                await self.cache.clear_cache()
                invalidated_count = -1  # All cleared
            
            return {'invalidated': invalidated_count}
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return {'invalidated': 0, 'error': str(e)}
    
    async def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        if not self.is_initialized:
            await self.initialize()
        
        return self.whisper_service.get_supported_languages()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all services.
        
        Returns:
            Health check results
        """
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
            else:
                health['services']['initialization'] = 'healthy'
            
            # Check Whisper service
            if self.whisper_service and self.whisper_service._model_loaded:
                health['services']['whisper'] = 'healthy'
            else:
                health['services']['whisper'] = 'unhealthy'
                health['errors'].append('Whisper model not loaded')
                health['overall_status'] = 'degraded'
            
            # Check processor
            if self.enable_processing:
                if self.processor:
                    health['services']['processor'] = 'healthy'
                else:
                    health['services']['processor'] = 'unhealthy'
                    health['errors'].append('Processor not initialized')
                    health['overall_status'] = 'degraded'
            
            # Check cache
            if self.enable_cache:
                if self.cache:
                    health['services']['cache'] = 'healthy'
                else:
                    health['services']['cache'] = 'unhealthy'
                    health['errors'].append('Cache not initialized')
                    health['overall_status'] = 'degraded'
            
            # Check streaming
            if self.enable_streaming:
                if self.streaming_service:
                    health['services']['streaming'] = 'healthy'
                else:
                    health['services']['streaming'] = 'unhealthy'
                    health['errors'].append('Streaming service not initialized')
                    health['overall_status'] = 'degraded'
            
            # Add recent error info
            if self.stats['last_error']:
                health['last_error'] = self.stats['last_error']
                health['error_count'] = self.stats['errors']
            
        except Exception as e:
            health['overall_status'] = 'unhealthy'
            health['errors'].append(f'Health check failed: {str(e)}')
        
        return health
    
    async def shutdown(self) -> None:
        """Shutdown all services and cleanup resources."""
        try:
            logger.info("Shutting down STT Manager...")
            
            # Stop streaming if active
            if self.is_streaming_active:
                await self.stop_streaming()
            
            # Shutdown services
            if self.whisper_service:
                await self.whisper_service.shutdown()
            
            if self.cache:
                await self.cache.close()
            
            # Reset state
            self.is_initialized = False
            self.whisper_service = None
            self.processor = None
            self.cache = None
            self.streaming_service = None
            
            logger.success("STT Manager shutdown complete")
            
        except Exception as e:
            logger.error(f"STT Manager shutdown failed: {e}")


# Global STT manager instance
_stt_manager: Optional[STTManager] = None


def get_stt_manager() -> STTManager:
    """Get global STT manager instance."""
    global _stt_manager
    if _stt_manager is None:
        _stt_manager = STTManager()
    return _stt_manager