"""Text-to-Speech (TTS) services module.

This module provides comprehensive TTS capabilities with:
- Piper TTS engine with Italian voice support
- Advanced text preprocessing with emotion injection  
- Streaming audio response with buffer management
- Voice personalization based on context and user preferences
- Cultural adaptation and personality consistency
- Performance optimization and quality metrics
"""

from .piper_service import (
    PiperTTSService,
    TTSRequest,
    TTSResponse,
    VoiceModel,
    VoiceGender,
    VoiceLanguage,
    AudioFormat,
    ProsodySettings,
    SSMLSettings,
    ProsodyControl
)

from .tts_processor import (
    TTSProcessor,
    ProcessedText,
    ProcessingSettings,
    EmotionType,
    EmotionSettings,
    PauseType,
    CodeSwitchContext
)

from .audio_stream import (
    AudioResponseStream,
    StreamChunk,
    StreamingConfig,
    StreamingFormat,
    CompressionLevel,
    BufferStrategy,
    AudioBuffer,
    SilenceDetector,
    AudioCompressor
)

from .voice_personalizer import (
    VoicePersonalizer,
    PersonalizationProfile,
    UserPreferences,
    PersonalityType,
    CulturalStyle,
    SpeechStyle,
    ContextAdaptation
)

from .tts_manager import (
    TTSManager,
    TTSManagerConfig,
    SynthesisRequest,
    SynthesisResponse,
    get_tts_manager
)

__all__ = [
    # Core TTS Services
    'PiperTTSService',
    'TTSProcessor', 
    'AudioResponseStream',
    'VoicePersonalizer',
    'TTSManager',
    
    # TTS Service Components
    'TTSRequest',
    'TTSResponse',
    'VoiceModel',
    'ProsodySettings',
    'SSMLSettings',
    
    # Text Processing
    'ProcessedText',
    'ProcessingSettings',
    'EmotionSettings',
    
    # Audio Streaming
    'StreamChunk',
    'StreamingConfig',
    'AudioBuffer',
    'SilenceDetector',
    'AudioCompressor',
    
    # Voice Personalization
    'PersonalizationProfile',
    'UserPreferences',
    'ContextAdaptation',
    
    # Manager Components
    'TTSManagerConfig',
    'SynthesisRequest',
    'SynthesisResponse',
    
    # Enums
    'VoiceGender',
    'VoiceLanguage',
    'AudioFormat',
    'ProsodyControl',
    'EmotionType',
    'PauseType',
    'CodeSwitchContext',
    'StreamingFormat',
    'CompressionLevel',
    'BufferStrategy',
    'PersonalityType',
    'CulturalStyle',
    'SpeechStyle',
    
    # Factory functions
    'get_tts_manager',
    'create_piper_service',
    'create_tts_processor',
    'create_audio_stream',
    'create_voice_personalizer',
    'create_tts_stack',
]

# Version info
__version__ = "1.0.0"
__author__ = "VoiceHelpDeskAI Team"


def create_piper_service(
    models_dir: str = "./models/piper",
    cache_dir: str = "./cache/tts",
    enable_caching: bool = True,
    default_voice: str = "it-riccardo-x-low",
    fallback_voice: str = "en-us-amy-low"
) -> PiperTTSService:
    """Factory function to create Piper TTS service.
    
    Args:
        models_dir: Directory containing Piper voice models
        cache_dir: Directory for caching audio responses
        enable_caching: Enable audio response caching
        default_voice: Default voice ID to use
        fallback_voice: Fallback voice if default unavailable
        
    Returns:
        Configured PiperTTSService instance
    """
    return PiperTTSService(
        models_dir=models_dir,
        cache_dir=cache_dir,
        enable_caching=enable_caching,
        default_voice=default_voice,
        fallback_voice=fallback_voice
    )


def create_tts_processor(
    enable_advanced_processing: bool = True,
    enable_emotion_detection: bool = True,
    italian_pronunciation_dict: str = None
) -> TTSProcessor:
    """Factory function to create TTS processor.
    
    Args:
        enable_advanced_processing: Enable advanced text processing features
        enable_emotion_detection: Enable emotion detection from text
        italian_pronunciation_dict: Path to Italian pronunciation dictionary
        
    Returns:
        Configured TTSProcessor instance
    """
    return TTSProcessor(
        enable_advanced_processing=enable_advanced_processing,
        enable_emotion_detection=enable_emotion_detection,
        italian_pronunciation_dict=italian_pronunciation_dict
    )


def create_audio_stream(
    config: StreamingConfig = None,
    enable_real_time: bool = True,
    enable_adaptive_quality: bool = True
) -> AudioResponseStream:
    """Factory function to create audio response stream.
    
    Args:
        config: Streaming configuration
        enable_real_time: Enable real-time streaming optimizations
        enable_adaptive_quality: Enable adaptive quality based on conditions
        
    Returns:
        Configured AudioResponseStream instance
    """
    return AudioResponseStream(
        config=config,
        enable_real_time=enable_real_time,
        enable_adaptive_quality=enable_adaptive_quality
    )


def create_voice_personalizer(
    enable_user_learning: bool = True,
    enable_context_adaptation: bool = True,
    enable_cultural_adaptation: bool = True,
    adaptation_strength: float = 0.7
) -> VoicePersonalizer:
    """Factory function to create voice personalizer.
    
    Args:
        enable_user_learning: Enable learning from user feedback
        enable_context_adaptation: Enable context-based adaptations
        enable_cultural_adaptation: Enable cultural style adaptations
        adaptation_strength: Strength of personalization (0.0-1.0)
        
    Returns:
        Configured VoicePersonalizer instance
    """
    return VoicePersonalizer(
        enable_user_learning=enable_user_learning,
        enable_context_adaptation=enable_context_adaptation,
        enable_cultural_adaptation=enable_cultural_adaptation,
        adaptation_strength=adaptation_strength
    )


def create_tts_stack(
    models_dir: str = "./models/piper",
    cache_dir: str = "./cache/tts",
    enable_caching: bool = True,
    enable_streaming: bool = True,
    enable_personalization: bool = True,
    enable_advanced_processing: bool = True,
    default_voice_id: str = "it-riccardo-x-low",
    quality_level: str = "medium"
) -> tuple[PiperTTSService, TTSProcessor, VoicePersonalizer, TTSManager]:
    """Factory function to create complete TTS stack.
    
    Args:
        models_dir: Directory containing voice models
        cache_dir: Directory for caching
        enable_caching: Enable audio caching
        enable_streaming: Enable streaming audio
        enable_personalization: Enable voice personalization
        enable_advanced_processing: Enable advanced text processing
        default_voice_id: Default voice identifier
        quality_level: Audio quality level
        
    Returns:
        Tuple of (PiperTTSService, TTSProcessor, VoicePersonalizer, TTSManager)
    """
    # Create manager configuration
    config = TTSManagerConfig(
        models_dir=models_dir,
        cache_dir=cache_dir,
        enable_caching=enable_caching,
        enable_streaming=enable_streaming,
        enable_personalization=enable_personalization,
        enable_advanced_processing=enable_advanced_processing,
        default_voice_id=default_voice_id,
        quality_level=quality_level
    )
    
    # Create manager
    tts_manager = TTSManager(config)
    
    # Create individual components
    piper_service = create_piper_service(
        models_dir=models_dir,
        cache_dir=cache_dir,
        enable_caching=enable_caching,
        default_voice=default_voice_id
    )
    
    tts_processor = create_tts_processor(
        enable_advanced_processing=enable_advanced_processing,
        enable_emotion_detection=True
    ) if enable_advanced_processing else None
    
    voice_personalizer = create_voice_personalizer(
        enable_user_learning=True,
        enable_context_adaptation=True,
        enable_cultural_adaptation=True
    ) if enable_personalization else None
    
    return piper_service, tts_processor, voice_personalizer, tts_manager


# Convenience aliases for common patterns
from .piper_service import TTSResponse as AudioResponse
from .tts_processor import ProcessedText as TextAnalysis  
from .audio_stream import StreamChunk as AudioChunk
from .voice_personalizer import PersonalizationProfile as VoiceProfile
from .tts_manager import SynthesisResponse as SpeechResponse