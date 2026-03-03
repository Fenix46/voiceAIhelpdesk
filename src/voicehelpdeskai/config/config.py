"""Comprehensive configuration settings using Pydantic."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    # SQLite settings
    sqlite_path: str = Field(default="./app.db", description="SQLite database path")
    sqlite_check_same_thread: bool = Field(default=False, description="SQLite thread check")
    
    # Connection pool settings
    pool_size: int = Field(default=5, description="Database connection pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, description="Pool recycle time in seconds")
    
    # General database settings
    echo: bool = Field(default=False, description="SQLAlchemy echo mode")
    echo_pool: bool = Field(default=False, description="Echo connection pool")
    
    @validator("sqlite_path")
    def validate_sqlite_path(cls, v):
        """Ensure SQLite path is valid."""
        if not v.startswith(":memory:"):
            path = Path(v)
            path.parent.mkdir(parents=True, exist_ok=True)
        return v


class STTSettings(BaseSettings):
    """Speech-to-Text configuration settings."""
    
    # Whisper model settings
    whisper_model_size: str = Field(default="medium", description="Whisper model size")
    whisper_device: str = Field(default="auto", description="Device for Whisper inference")
    whisper_compute_type: str = Field(default="auto", description="Compute type for quantization")
    whisper_cpu_threads: int = Field(default=0, description="CPU threads for Whisper (0=auto)")
    whisper_language: str = Field(default="it", description="Default language for Whisper")
    
    # Processing settings
    enable_post_processing: bool = Field(default=True, description="Enable transcription post-processing")
    enable_punctuation: bool = Field(default=True, description="Enable punctuation normalization")
    enable_number_normalization: bool = Field(default=True, description="Enable number normalization")
    enable_acronym_expansion: bool = Field(default=True, description="Enable IT acronym expansion")
    enable_profanity_filter: bool = Field(default=True, description="Enable profanity filtering")
    enable_spell_correction: bool = Field(default=True, description="Enable Italian spell correction")
    enable_ner: bool = Field(default=True, description="Enable named entity recognition")
    
    # Streaming settings
    enable_streaming: bool = Field(default=True, description="Enable streaming transcription")
    chunk_duration: float = Field(default=1.0, description="Audio chunk duration in seconds")
    overlap_duration: float = Field(default=0.2, description="Chunk overlap duration in seconds")
    enable_vad: bool = Field(default=True, description="Enable voice activity detection")
    enable_context_correction: bool = Field(default=True, description="Enable context-based corrections")
    enable_interruption_detection: bool = Field(default=True, description="Enable interruption detection")
    
    # Cache settings
    enable_caching: bool = Field(default=True, description="Enable transcription caching")
    cache_ttl: int = Field(default=86400, description="Cache TTL in seconds (24h)")
    cache_compression: bool = Field(default=True, description="Enable cache compression")
    enable_fuzzy_matching: bool = Field(default=True, description="Enable fuzzy audio matching")
    fuzzy_threshold: float = Field(default=0.85, description="Fuzzy matching similarity threshold")
    max_fuzzy_candidates: int = Field(default=10, description="Maximum fuzzy match candidates")
    max_memory_cache: int = Field(default=1000, description="Maximum memory cache entries")
    
    # Performance settings
    whisper_num_workers: int = Field(default=2, description="Number of Whisper workers")
    enable_warmup: bool = Field(default=True, description="Enable service warmup")
    
    @validator("whisper_model_size")
    def validate_whisper_model_size(cls, v):
        """Validate Whisper model size."""
        valid_sizes = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
        if v not in valid_sizes:
            raise ValueError(f"Whisper model size must be one of: {valid_sizes}")
        return v
    
    @validator("whisper_device")
    def validate_whisper_device(cls, v):
        """Validate Whisper device setting."""
        if v not in ["auto", "cpu", "cuda", "mps"]:
            raise ValueError("Whisper device must be one of: auto, cpu, cuda, mps")
        return v
    
    @validator("whisper_compute_type")
    def validate_compute_type(cls, v):
        """Validate compute type."""
        valid_types = ["auto", "int8", "int16", "float16", "float32"]
        if v not in valid_types:
            raise ValueError(f"Compute type must be one of: {valid_types}")
        return v
    
    @validator("fuzzy_threshold")
    def validate_fuzzy_threshold(cls, v):
        """Validate fuzzy matching threshold."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Fuzzy threshold must be between 0.0 and 1.0")
        return v


class LLMSettings(BaseSettings):
    """Large Language Model configuration settings."""
    
    # Model selection
    model_name: str = Field(default="gemma3-1B", description="LLM model name")
    backend: str = Field(default="transformers", description="LLM backend (transformers, ollama, llama_cpp, vllm, openai)")
    quantization: str = Field(default="int8", description="Quantization type (none, int4, int8, fp16, bf16)")
    
    # Model configuration
    context_length: int = Field(default=8192, description="Model context length")
    max_tokens: int = Field(default=1024, description="Maximum output tokens")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    top_p: float = Field(default=0.9, description="Top-p sampling")
    top_k: int = Field(default=40, description="Top-k sampling")
    repetition_penalty: float = Field(default=1.0, description="Repetition penalty")
    
    # Memory optimization
    optimize_for_8gb: bool = Field(default=True, description="Optimize for 8GB GPU")
    gpu_layers: int = Field(default=-1, description="Number of GPU layers (-1 for auto)")
    batch_size: int = Field(default=1, description="Batch size for inference")
    
    # Features
    enable_rag: bool = Field(default=True, description="Enable RAG capabilities")
    enable_function_calling: bool = Field(default=True, description="Enable function calling")
    enable_conversation_management: bool = Field(default=True, description="Enable conversation tracking")
    enable_prompt_management: bool = Field(default=True, description="Enable advanced prompt features")
    
    # Conversation settings
    max_conversation_length: int = Field(default=8000, description="Max conversation context length")
    summarization_threshold: int = Field(default=20, description="Messages before auto-summarization")
    auto_summarize: bool = Field(default=True, description="Enable automatic summarization")
    sentiment_tracking: bool = Field(default=True, description="Enable sentiment analysis")
    entity_tracking: bool = Field(default=True, description="Enable entity extraction")
    conversation_timeout: int = Field(default=3600, description="Conversation timeout in seconds")
    
    # Prompt management
    enable_ab_testing: bool = Field(default=True, description="Enable prompt A/B testing")
    enable_performance_tracking: bool = Field(default=True, description="Enable performance tracking")
    auto_optimization: bool = Field(default=True, description="Enable automatic prompt optimization")
    
    # Caching
    enable_response_caching: bool = Field(default=True, description="Enable response caching")
    cache_size: int = Field(default=100, description="Response cache size")
    strategic_caching: bool = Field(default=True, description="Enable strategic response caching")
    
    # Performance settings
    enable_warmup: bool = Field(default=True, description="Enable model warmup")
    num_workers: int = Field(default=2, description="Number of worker threads")
    
    @validator("backend")
    def validate_backend(cls, v):
        """Validate LLM backend."""
        valid_backends = ["transformers", "ollama", "llama_cpp", "vllm", "openai"]
        if v not in valid_backends:
            raise ValueError(f"Backend must be one of: {valid_backends}")
        return v
    
    @validator("quantization")
    def validate_quantization(cls, v):
        """Validate quantization type."""
        valid_types = ["none", "int4", "int8", "fp16", "bf16"]
        if v not in valid_types:
            raise ValueError(f"Quantization must be one of: {valid_types}")
        return v
    
    @validator("temperature")
    def validate_temperature(cls, v):
        """Validate temperature."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v
    
    @validator("top_p")
    def validate_top_p(cls, v):
        """Validate top_p."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Top_p must be between 0.0 and 1.0")
        return v


class NLUSettings(BaseSettings):
    """Natural Language Understanding configuration settings."""
    
    # Model configuration
    model_name: str = Field(default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", description="Sentence transformer model name")
    language: str = Field(default="it", description="Primary language for NLU processing")
    
    # Service enablement
    enable_intent_classification: bool = Field(default=True, description="Enable intent classification")
    enable_entity_extraction: bool = Field(default=True, description="Enable entity extraction")
    enable_problem_analysis: bool = Field(default=True, description="Enable problem analysis")
    enable_dialogue_tracking: bool = Field(default=True, description="Enable dialogue state tracking")
    
    # Intent Classification settings
    intent_confidence_threshold: float = Field(default=0.7, description="Minimum confidence for intent predictions")
    intent_fallback_threshold: float = Field(default=0.5, description="Threshold for LLM fallback")
    enable_intent_llm_fallback: bool = Field(default=True, description="Enable LLM fallback for ambiguous intents")
    intent_cache_embeddings: bool = Field(default=True, description="Cache text embeddings for performance")
    
    # Entity Extraction settings
    entity_fuzzy_threshold: float = Field(default=0.8, description="Fuzzy matching threshold for entity correction")
    enable_entity_fuzzy_matching: bool = Field(default=True, description="Enable fuzzy matching for entity typos")
    enable_entity_validation: bool = Field(default=True, description="Enable entity validation rules")
    enable_spacy_ner: bool = Field(default=True, description="Enable spaCy named entity recognition")
    
    # Problem Analysis settings
    problem_similarity_threshold: float = Field(default=0.75, description="Threshold for problem similarity matching")
    enable_problem_clustering: bool = Field(default=True, description="Enable automatic problem clustering")
    enable_solution_matching: bool = Field(default=True, description="Enable automatic solution template matching")
    max_similar_problems: int = Field(default=5, description="Maximum number of similar problems to return")
    
    # Dialogue State Tracking settings
    dialogue_context_timeout: int = Field(default=3600, description="Dialogue context timeout in seconds")
    max_turns_per_state: int = Field(default=5, description="Maximum turns allowed in same dialogue state")
    enable_proactive_suggestions: bool = Field(default=True, description="Enable proactive dialogue suggestions")
    enable_context_inference: bool = Field(default=True, description="Enable context inference from dialogue")
    
    # Performance and optimization
    batch_processing_size: int = Field(default=32, description="Batch size for processing multiple texts")
    enable_performance_tracking: bool = Field(default=True, description="Enable detailed performance tracking")
    enable_warmup: bool = Field(default=True, description="Enable service warmup on initialization")
    
    # Training and learning
    enable_online_learning: bool = Field(default=False, description="Enable online learning from user feedback")
    training_data_retention_days: int = Field(default=90, description="Days to retain training data")
    min_confidence_for_learning: float = Field(default=0.8, description="Minimum confidence for automatic learning")
    
    @validator("intent_confidence_threshold", "intent_fallback_threshold", "entity_fuzzy_threshold", "problem_similarity_threshold", "min_confidence_for_learning")
    def validate_thresholds(cls, v):
        """Validate threshold values are between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        return v
    
    @validator("language")
    def validate_language(cls, v):
        """Validate language code."""
        supported_languages = ["it", "en", "es", "fr", "de"]
        if v not in supported_languages:
            raise ValueError(f"Language must be one of: {supported_languages}")
        return v
    
    @validator("dialogue_context_timeout")
    def validate_context_timeout(cls, v):
        """Validate context timeout is reasonable."""
        if not 300 <= v <= 86400:  # 5 minutes to 24 hours
            raise ValueError("Context timeout must be between 300 and 86400 seconds")
        return v
    
    @validator("max_turns_per_state")
    def validate_max_turns(cls, v):
        """Validate maximum turns per state."""
        if not 1 <= v <= 20:
            raise ValueError("Max turns per state must be between 1 and 20")
        return v


class TTSSettings(BaseSettings):
    """Text-to-Speech configuration settings."""
    
    # Model configuration
    model_name: str = Field(default="qwen3-tts-1.7b-12hz-voicedesign", description="TTS model name")
    models_dir: str = Field(default="./models/piper", description="Directory containing Piper voice models")
    cache_dir: str = Field(default="./cache/tts", description="Directory for caching generated audio")
    default_voice_id: str = Field(default="it-riccardo-x-low", description="Default voice identifier")
    fallback_voice_id: str = Field(default="en-us-amy-low", description="Fallback voice if default unavailable")
    language: str = Field(default="it", description="Primary language for TTS")
    
    # Service enablement
    enable_caching: bool = Field(default=True, description="Enable audio response caching")
    enable_streaming: bool = Field(default=True, description="Enable streaming audio response")
    enable_personalization: bool = Field(default=True, description="Enable voice personalization")
    enable_advanced_processing: bool = Field(default=True, description="Enable advanced text processing")
    
    # Audio quality settings
    quality_level: str = Field(default="medium", description="Audio quality level (low, medium, high)")
    sample_rate: int = Field(default=22050, description="Audio sample rate in Hz")
    audio_format: str = Field(default="wav", description="Default audio format (wav, mp3, ogg)")
    bit_depth: int = Field(default=16, description="Audio bit depth")
    channels: int = Field(default=1, description="Number of audio channels")
    
    # Text processing settings
    enable_number_normalization: bool = Field(default=True, description="Enable Italian number normalization")
    enable_date_normalization: bool = Field(default=True, description="Enable date normalization")
    enable_acronym_expansion: bool = Field(default=True, description="Enable IT acronym expansion")
    enable_it_pronunciation: bool = Field(default=True, description="Enable Italian pronunciation guide")
    enable_emotion_injection: bool = Field(default=True, description="Enable emotion injection in speech")
    enable_pause_insertion: bool = Field(default=True, description="Enable intelligent pause insertion")
    enable_code_switching: bool = Field(default=True, description="Enable code-switching for technical terms")
    
    # Personalization settings
    enable_user_learning: bool = Field(default=True, description="Enable learning from user feedback")
    enable_context_adaptation: bool = Field(default=True, description="Enable context-based voice adaptation")
    enable_cultural_adaptation: bool = Field(default=True, description="Enable cultural style adaptation")
    adaptation_strength: float = Field(default=0.7, description="Strength of personalization (0.0-1.0)")
    
    # Streaming settings
    chunk_size: int = Field(default=1024, description="Audio chunk size for streaming")
    buffer_size: int = Field(default=8192, description="Buffer size for streaming")
    enable_compression: bool = Field(default=True, description="Enable audio compression for streaming")
    compression_level: str = Field(default="medium", description="Compression level (low, medium, high)")
    enable_silence_detection: bool = Field(default=True, description="Enable silence detection for optimization")
    
    # Performance settings
    max_text_length: int = Field(default=1000, description="Maximum text length for synthesis")
    cache_ttl: int = Field(default=86400, description="Cache TTL in seconds (24h)")
    max_cache_size: int = Field(default=1000, description="Maximum number of cached audio responses")
    enable_warmup: bool = Field(default=True, description="Enable service warmup on initialization")
    
    # Voice model settings
    enable_voice_fallback: bool = Field(default=True, description="Enable fallback to available voices")
    voice_selection_mode: str = Field(default="auto", description="Voice selection mode (auto, manual)")
    gender_preference: str = Field(default="neutral", description="Default gender preference (male, female, neutral)")
    
    @validator("quality_level")
    def validate_quality_level(cls, v):
        """Validate quality level."""
        valid_levels = ["low", "medium", "high"]
        if v not in valid_levels:
            raise ValueError(f"Quality level must be one of: {valid_levels}")
        return v
    
    @validator("audio_format")
    def validate_audio_format(cls, v):
        """Validate audio format."""
        valid_formats = ["wav", "mp3", "ogg", "flac"]
        if v not in valid_formats:
            raise ValueError(f"Audio format must be one of: {valid_formats}")
        return v
    
    @validator("sample_rate")
    def validate_sample_rate(cls, v):
        """Validate sample rate."""
        valid_rates = [8000, 16000, 22050, 44100, 48000]
        if v not in valid_rates:
            raise ValueError(f"Sample rate must be one of: {valid_rates}")
        return v
    
    @validator("bit_depth")
    def validate_bit_depth(cls, v):
        """Validate bit depth."""
        valid_depths = [8, 16, 24, 32]
        if v not in valid_depths:
            raise ValueError(f"Bit depth must be one of: {valid_depths}")
        return v
    
    @validator("channels")
    def validate_channels(cls, v):
        """Validate number of channels."""
        if not 1 <= v <= 2:
            raise ValueError("Channels must be 1 (mono) or 2 (stereo)")
        return v
    
    @validator("adaptation_strength")
    def validate_adaptation_strength(cls, v):
        """Validate adaptation strength."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Adaptation strength must be between 0.0 and 1.0")
        return v
    
    @validator("compression_level")
    def validate_compression_level(cls, v):
        """Validate compression level."""
        valid_levels = ["none", "low", "medium", "high", "adaptive"]
        if v not in valid_levels:
            raise ValueError(f"Compression level must be one of: {valid_levels}")
        return v
    
    @validator("voice_selection_mode")
    def validate_voice_selection_mode(cls, v):
        """Validate voice selection mode."""
        valid_modes = ["auto", "manual", "random"]
        if v not in valid_modes:
            raise ValueError(f"Voice selection mode must be one of: {valid_modes}")
        return v
    
    @validator("gender_preference")
    def validate_gender_preference(cls, v):
        """Validate gender preference."""
        valid_genders = ["male", "female", "neutral"]
        if v not in valid_genders:
            raise ValueError(f"Gender preference must be one of: {valid_genders}")
        return v


class AIModelSettings(BaseSettings):
    """AI Models configuration settings."""
    
    # Model paths
    model_cache_dir: str = Field(default="./models", description="Model cache directory")
    whisper_model_path: Optional[str] = Field(default=None, description="Custom Whisper model path")
    llm_model_path: Optional[str] = Field(default=None, description="Custom LLM model path")
    tts_model_path: Optional[str] = Field(default=None, description="Custom TTS model path")
    
    # Quantization settings
    use_quantization: bool = Field(default=False, description="Enable model quantization")
    quantization_bits: int = Field(default=8, description="Quantization bits (4, 8, 16)")
    
    # Token limits
    max_input_tokens: int = Field(default=4096, description="Maximum input tokens")
    max_output_tokens: int = Field(default=1000, description="Maximum output tokens")
    max_total_tokens: int = Field(default=8192, description="Maximum total tokens")
    
    # Performance settings
    batch_size: int = Field(default=1, description="Model batch size")
    num_workers: int = Field(default=1, description="Number of worker processes")
    device: str = Field(default="auto", description="Device for inference (auto, cpu, cuda)")
    
    @validator("quantization_bits")
    def validate_quantization_bits(cls, v):
        """Validate quantization bits."""
        if v not in [4, 8, 16]:
            raise ValueError("Quantization bits must be 4, 8, or 16")
        return v
    
    @validator("device")
    def validate_device(cls, v):
        """Validate device setting."""
        if v not in ["auto", "cpu", "cuda", "mps"]:
            raise ValueError("Device must be one of: auto, cpu, cuda, mps")
        return v


class AudioSettings(BaseSettings):
    """Audio processing configuration settings."""
    
    # Basic audio settings
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    chunk_size: int = Field(default=1024, description="Audio chunk size")
    format: str = Field(default="wav", description="Default audio format")
    
    # Processing settings
    silence_threshold: float = Field(default=0.01, description="Silence detection threshold")
    silence_duration: float = Field(default=1.0, description="Silence duration in seconds")
    max_audio_length: int = Field(default=300, description="Max audio length in seconds")
    min_audio_length: float = Field(default=0.5, description="Min audio length in seconds")
    
    # Noise reduction
    enable_noise_reduction: bool = Field(default=True, description="Enable noise reduction")
    noise_reduction_strength: float = Field(default=0.5, description="Noise reduction strength")
    
    # Audio enhancement
    enable_auto_gain: bool = Field(default=True, description="Enable automatic gain control")
    normalize_audio: bool = Field(default=True, description="Normalize audio levels")
    
    # File settings
    supported_formats: List[str] = Field(
        default=["wav", "mp3", "m4a", "ogg", "flac"], 
        description="Supported audio formats"
    )
    audio_storage_path: str = Field(default="./audio_files", description="Audio storage path")
    temp_audio_path: str = Field(default="./temp_audio", description="Temporary audio path")
    
    @validator("sample_rate")
    def validate_sample_rate(cls, v):
        """Validate sample rate."""
        valid_rates = [8000, 16000, 22050, 44100, 48000]
        if v not in valid_rates:
            raise ValueError(f"Sample rate must be one of: {valid_rates}")
        return v
    
    @validator("silence_threshold")
    def validate_silence_threshold(cls, v):
        """Validate silence threshold."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Silence threshold must be between 0.0 and 1.0")
        return v


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    # Connection settings
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: Optional[str] = Field(default=None, description="Redis password")
    database: int = Field(default=0, description="Redis database number")
    
    # Connection pool settings
    max_connections: int = Field(default=20, description="Max Redis connections")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    socket_timeout: int = Field(default=30, description="Socket timeout in seconds")
    
    # Cache settings
    default_ttl: int = Field(default=3600, description="Default TTL in seconds")
    session_ttl: int = Field(default=86400, description="Session TTL in seconds")
    cache_prefix: str = Field(default="voicehelpdesk:", description="Cache key prefix")
    
    # Specific TTLs
    audio_cache_ttl: int = Field(default=1800, description="Audio cache TTL")
    transcription_cache_ttl: int = Field(default=7200, description="Transcription cache TTL")
    ai_response_cache_ttl: int = Field(default=3600, description="AI response cache TTL")


class APISettings(BaseSettings):
    """API configuration settings."""
    
    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins"
    )
    cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed CORS methods"
    )
    cors_headers: List[str] = Field(
        default=["*"],
        description="Allowed CORS headers"
    )
    cors_credentials: bool = Field(default=True, description="Allow CORS credentials")
    
    # Rate limiting
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=100, description="Requests per minute")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")
    rate_limit_per_ip: bool = Field(default=True, description="Rate limit per IP")
    
    # Authentication
    jwt_secret_key: str = Field(description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration: int = Field(default=3600, description="JWT expiration in seconds")
    
    # API limits
    max_request_size: int = Field(default=50*1024*1024, description="Max request size in bytes")
    max_file_upload_size: int = Field(default=100*1024*1024, description="Max file upload size")
    
    # Security
    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        description="Allowed hosts"
    )
    trusted_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        description="Trusted hosts"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    # Basic logging
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json, text)")
    
    # File logging
    file_path: str = Field(default="./logs/app.log", description="Log file path")
    max_file_size: str = Field(default="10MB", description="Max log file size")
    backup_count: int = Field(default=5, description="Number of backup log files")
    
    # Console logging
    enable_console: bool = Field(default=True, description="Enable console logging")
    console_level: str = Field(default="INFO", description="Console log level")
    
    # Structured logging
    include_timestamp: bool = Field(default=True, description="Include timestamp")
    include_caller: bool = Field(default=True, description="Include caller info")
    include_process: bool = Field(default=False, description="Include process info")
    
    # Third-party loggers
    sqlalchemy_log_level: str = Field(default="WARNING", description="SQLAlchemy log level")
    uvicorn_log_level: str = Field(default="INFO", description="Uvicorn log level")
    celery_log_level: str = Field(default="INFO", description="Celery log level")
    
    # Log filtering
    sensitive_fields: List[str] = Field(
        default=["password", "token", "api_key", "secret"],
        description="Fields to mask in logs"
    )
    
    @validator("level", "console_level", "sqlalchemy_log_level", "uvicorn_log_level", "celery_log_level")
    def validate_log_levels(cls, v):
        """Validate log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="VOICEHELPDESK_"
    )
    
    # Application info
    app_name: str = Field(default="VoiceHelpDeskAI", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Environment")
    debug: bool = Field(default=True, description="Debug mode")
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of workers")
    
    # API settings
    api_v1_str: str = Field(default="/api/v1", description="API v1 prefix")
    
    # Configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ai_models: AIModelSettings = Field(default_factory=AIModelSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    nlu: NLUSettings = Field(default_factory=NLUSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    # Feature flags
    features: Dict[str, bool] = Field(
        default={
            "voice_chat": True,
            "file_upload": True,
            "real_time_streaming": True,
            "analytics": False,
            "metrics": True,
            "background_tasks": True,
        },
        description="Feature flags"
    )
    
    # Development settings
    hot_reload: bool = Field(default=True, description="Enable hot reload in development")
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment.lower() == "testing"
    
    @property
    def database_url(self) -> str:
        """Generate database URL."""
        return f"sqlite:///{self.database.sqlite_path}"
    
    @property
    def redis_url(self) -> str:
        """Generate Redis URL."""
        auth = f":{self.redis.password}@" if self.redis.password else ""
        return f"redis://{auth}{self.redis.host}:{self.redis.port}/{self.redis.database}"
    
    def get_feature(self, feature_name: str) -> bool:
        """Get feature flag value."""
        return self.features.get(feature_name, False)
    
    def set_feature(self, feature_name: str, enabled: bool) -> None:
        """Set feature flag value."""
        self.features[feature_name] = enabled


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
