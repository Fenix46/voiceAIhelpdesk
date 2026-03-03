"""Speech-to-Text (STT) services module.

This module provides advanced speech recognition capabilities with:
- Whisper model integration with optimizations
- Italian language support and dialect handling
- Real-time streaming transcription
- Post-processing and text enhancement
- Intelligent caching with fuzzy matching
- Context-aware corrections
"""

from .whisper_service import (
    WhisperService,
    TranscriptionResult,
    WordTimestamp
)
from .transcription_processor import (
    TranscriptionProcessor, 
    ProcessedTranscription
)
from .continuous_stream import (
    ContinuousTranscriptionStream,
    StreamingTranscription,
    TranscriptionState
)
from .transcription_cache import (
    TranscriptionCache,
    CacheEntry,
    AudioFeatures
)

__all__ = [
    # Core services
    'WhisperService',
    'TranscriptionProcessor',
    'ContinuousTranscriptionStream',
    'TranscriptionCache',
    
    # Data models
    'TranscriptionResult',
    'ProcessedTranscription',
    'StreamingTranscription',
    'WordTimestamp',
    'CacheEntry',
    'AudioFeatures',
    
    # Enums
    'TranscriptionState',
    
    # Factory functions
    'create_stt_service',
    'create_streaming_service',
]

# Version info
__version__ = "1.0.0"
__author__ = "VoiceHelpDeskAI Team"


def create_stt_service(
    model_size: str = "medium",
    device: str = "auto",
    enable_cache: bool = True,
    cache_ttl: int = 86400,
    enable_processing: bool = True,
    language: str = "it"
) -> tuple[WhisperService, TranscriptionProcessor, TranscriptionCache]:
    """Factory function to create a complete STT service stack.
    
    Args:
        model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
        device: Device to use (auto, cpu, cuda)
        enable_cache: Enable transcription caching
        cache_ttl: Cache time-to-live in seconds
        enable_processing: Enable post-processing
        language: Primary language for optimizations
        
    Returns:
        Tuple of (WhisperService, TranscriptionProcessor, TranscriptionCache)
    """
    # Create Whisper service
    whisper_service = WhisperService(
        model_size=model_size,
        device=device
    )
    
    # Create transcription processor
    processor = None
    if enable_processing:
        processor = TranscriptionProcessor(
            enable_punctuation=True,
            enable_number_normalization=True,
            enable_acronym_expansion=True,
            enable_profanity_filter=True,
            enable_ner=True,
            enable_spell_correction=True
        )
    
    # Create cache
    cache = None
    if enable_cache:
        cache = TranscriptionCache(
            ttl_seconds=cache_ttl,
            enable_compression=True,
            enable_fuzzy_matching=True,
            fuzzy_threshold=0.85
        )
    
    return whisper_service, processor, cache


def create_streaming_service(
    whisper_service: WhisperService,
    transcription_processor: TranscriptionProcessor = None,
    chunk_duration: float = 1.0,
    overlap_duration: float = 0.2,
    enable_vad: bool = True,
    enable_context_correction: bool = True,
    language: str = "it"
) -> ContinuousTranscriptionStream:
    """Factory function to create a streaming transcription service.
    
    Args:
        whisper_service: WhisperService instance
        transcription_processor: Optional TranscriptionProcessor
        chunk_duration: Duration of audio chunks in seconds
        overlap_duration: Overlap between chunks in seconds
        enable_vad: Enable voice activity detection
        enable_context_correction: Enable context-based corrections
        language: Target language
        
    Returns:
        ContinuousTranscriptionStream instance
    """
    return ContinuousTranscriptionStream(
        whisper_service=whisper_service,
        transcription_processor=transcription_processor,
        chunk_duration=chunk_duration,
        overlap_duration=overlap_duration,
        enable_vad=enable_vad,
        enable_context_correction=enable_context_correction,
        enable_interruption_detection=True,
        language=language
    )


# Convenience imports for common usage patterns
from .whisper_service import TranscriptionResult as STTResult
from .transcription_processor import ProcessedTranscription as ProcessedSTT
from .continuous_stream import StreamingTranscription as StreamingSTT