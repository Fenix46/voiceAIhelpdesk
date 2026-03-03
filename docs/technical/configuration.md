# Configuration Reference

## Table of Contents
1. [Overview](#overview)
2. [Environment Variables](#environment-variables)
3. [Configuration Files](#configuration-files)
4. [AI Model Configuration](#ai-model-configuration)
5. [Database Configuration](#database-configuration)
6. [Security Configuration](#security-configuration)
7. [Monitoring Configuration](#monitoring-configuration)
8. [Performance Tuning](#performance-tuning)
9. [Environment-Specific Settings](#environment-specific-settings)

## Overview

VoiceHelpDeskAI uses a hierarchical configuration system that prioritizes environment variables over configuration files. This design ensures flexibility across different deployment environments while maintaining security best practices.

### Configuration Priority (highest to lowest)
1. **Environment Variables** - Runtime configuration
2. **Configuration Files** - Static configuration
3. **Default Values** - Fallback values

### Configuration Sources
- **Environment Variables**: `.env` files, system environment
- **Configuration Files**: `config/`, YAML/JSON files
- **Command Line**: CLI arguments (limited use)
- **External**: HashiCorp Vault, AWS Parameter Store

## Environment Variables

### Application Settings

#### Core Application
```bash
# Application Environment
VOICEHELPDESK_ENV=production                    # Environment: development, staging, production
VOICEHELPDESK_DEBUG=false                       # Enable debug mode (boolean)
VOICEHELPDESK_VERSION=1.0.0                     # Application version
VOICEHELPDESK_SECRET_KEY=your-secret-key-here   # Secret key for encryption (required)

# Server Configuration
VOICEHELPDESK_HOST=0.0.0.0                      # Server bind address
VOICEHELPDESK_PORT=8000                         # Server port
VOICEHELPDESK_WORKERS=4                         # Number of worker processes
VOICEHELPDESK_MAX_CONNECTIONS=1000              # Maximum concurrent connections
VOICEHELPDESK_TIMEOUT=30                        # Request timeout in seconds

# CORS and Security
VOICEHELPDESK_ALLOWED_HOSTS=localhost,yourdomain.com  # Allowed hosts (comma-separated)
VOICEHELPDESK_CORS_ORIGINS=https://yourdomain.com     # CORS origins (comma-separated)
VOICEHELPDESK_CORS_METHODS=GET,POST,PUT,DELETE        # Allowed HTTP methods
VOICEHELPDESK_CORS_HEADERS=*                          # Allowed headers
```

#### Logging Configuration
```bash
# Logging Settings
VOICEHELPDESK_LOG_LEVEL=INFO                    # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
VOICEHELPDESK_LOG_FILE=/app/logs/app.log        # Main log file path
VOICEHELPDESK_ERROR_LOG_FILE=/app/logs/error.log # Error log file path
VOICEHELPDESK_SECURITY_LOG_FILE=/app/logs/security.log # Security log file
VOICEHELPDESK_PERF_LOG_FILE=/app/logs/performance.log # Performance log file

# Log Rotation
VOICEHELPDESK_LOG_MAX_SIZE=100MB                # Max log file size before rotation
VOICEHELPDESK_LOG_RETENTION=30                  # Days to retain log files
VOICEHELPDESK_LOG_COMPRESSION=true              # Compress rotated logs

# Structured Logging
VOICEHELPDESK_LOG_FORMAT=json                   # Log format: json, text
VOICEHELPDESK_LOG_INCLUDE_TRACE=false           # Include stack traces in logs
```

### Database Configuration

#### Primary Database
```bash
# Database Connection
VOICEHELPDESK_DATABASE_URL=postgresql://user:password@localhost:5432/voicehelpdesk  # Full database URL
VOICEHELPDESK_DB_HOST=localhost                 # Database host
VOICEHELPDESK_DB_PORT=5432                      # Database port
VOICEHELPDESK_DB_NAME=voicehelpdesk            # Database name
VOICEHELPDESK_DB_USER=voicehelpdesk            # Database username
VOICEHELPDESK_DB_PASSWORD=password             # Database password

# Connection Pool Settings
VOICEHELPDESK_DB_POOL_SIZE=20                   # Connection pool size
VOICEHELPDESK_DB_MAX_OVERFLOW=30                # Maximum overflow connections
VOICEHELPDESK_DB_POOL_TIMEOUT=30                # Connection timeout (seconds)
VOICEHELPDESK_DB_POOL_RECYCLE=3600             # Connection recycle time (seconds)
VOICEHELPDESK_DB_POOL_PRE_PING=true            # Validate connections before use

# Query Settings
VOICEHELPDESK_DB_ECHO=false                     # Echo SQL queries (debug mode)
VOICEHELPDESK_DB_QUERY_TIMEOUT=30               # Query timeout (seconds)
```

#### Redis Configuration
```bash
# Redis Connection
VOICEHELPDESK_REDIS_URL=redis://localhost:6379/0  # Full Redis URL
VOICEHELPDESK_REDIS_HOST=localhost              # Redis host
VOICEHELPDESK_REDIS_PORT=6379                   # Redis port
VOICEHELPDESK_REDIS_DB=0                        # Redis database number
VOICEHELPDESK_REDIS_PASSWORD=                   # Redis password (if required)

# Redis Pool Settings
VOICEHELPDESK_REDIS_POOL_SIZE=20                # Connection pool size
VOICEHELPDESK_REDIS_POOL_MAX_CONNECTIONS=50     # Maximum connections
VOICEHELPDESK_REDIS_SOCKET_TIMEOUT=5            # Socket timeout (seconds)
VOICEHELPDESK_REDIS_SOCKET_KEEPALIVE=true       # Enable socket keep-alive

# Cache Settings
VOICEHELPDESK_CACHE_TTL=300                     # Default cache TTL (seconds)
VOICEHELPDESK_SESSION_TTL=3600                  # Session TTL (seconds)
VOICEHELPDESK_RATE_LIMIT_TTL=3600              # Rate limit window (seconds)
```

### AI Model Configuration

#### Speech-to-Text (Whisper)
```bash
# Whisper Model Settings
VOICEHELPDESK_WHISPER_MODEL=base                # Model size: tiny, base, small, medium, large
VOICEHELPDESK_WHISPER_DEVICE=auto               # Device: auto, cpu, cuda
VOICEHELPDESK_WHISPER_LANGUAGE=auto             # Default language: auto, en, es, fr, etc.
VOICEHELPDESK_WHISPER_TEMPERATURE=0.0           # Sampling temperature (0.0-1.0)
VOICEHELPDESK_WHISPER_BEAM_SIZE=5               # Beam search size
VOICEHELPDESK_WHISPER_PATIENCE=1.0              # Beam search patience

# Model Paths
VOICEHELPDESK_MODEL_PATH=/app/models            # Base path for model files
VOICEHELPDESK_WHISPER_MODEL_PATH=/app/models/whisper  # Whisper models directory
VOICEHELPDESK_WHISPER_CACHE_DIR=/tmp/whisper    # Model cache directory

# Performance Settings
VOICEHELPDESK_WHISPER_FP16=true                 # Use FP16 precision (GPU only)
VOICEHELPDESK_WHISPER_BATCH_SIZE=1              # Batch size for inference
VOICEHELPDESK_WHISPER_MAX_LENGTH=30             # Maximum audio length (seconds)
```

#### Language Model (LLM)
```bash
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here         # OpenAI API key (required)
VOICEHELPDESK_LLM_PROVIDER=openai               # LLM provider: openai, azure, anthropic
VOICEHELPDESK_LLM_MODEL=gpt-3.5-turbo           # Model name
VOICEHELPDESK_LLM_API_BASE=https://api.openai.com/v1  # API base URL
VOICEHELPDESK_LLM_API_VERSION=2023-12-01        # API version (for Azure)

# Generation Settings
VOICEHELPDESK_LLM_MAX_TOKENS=150                # Maximum tokens per response
VOICEHELPDESK_LLM_TEMPERATURE=0.7               # Response creativity (0.0-2.0)
VOICEHELPDESK_LLM_TOP_P=1.0                     # Nucleus sampling parameter
VOICEHELPDESK_LLM_FREQUENCY_PENALTY=0.0         # Frequency penalty (-2.0 to 2.0)
VOICEHELPDESK_LLM_PRESENCE_PENALTY=0.0          # Presence penalty (-2.0 to 2.0)

# Request Settings
VOICEHELPDESK_LLM_TIMEOUT=30                    # Request timeout (seconds)
VOICEHELPDESK_LLM_MAX_RETRIES=3                 # Maximum retry attempts
VOICEHELPDESK_LLM_BACKOFF_FACTOR=2              # Exponential backoff factor
```

#### Text-to-Speech (Piper)
```bash
# Piper TTS Settings
VOICEHELPDESK_PIPER_MODEL=en_US-amy-medium      # Voice model name
VOICEHELPDESK_PIPER_MODEL_PATH=/app/models/piper  # Piper models directory
VOICEHELPDESK_PIPER_SPEAKER_ID=0                # Speaker ID (for multi-speaker models)
VOICEHELPDESK_PIPER_SPEED=1.0                   # Speech speed multiplier
VOICEHELPDESK_PIPER_NOISE_SCALE=0.667           # Noise scale for variability
VOICEHELPDESK_PIPER_LENGTH_SCALE=1.0            # Length scale for timing

# Audio Output Settings
VOICEHELPDESK_TTS_SAMPLE_RATE=22050             # Output sample rate
VOICEHELPDESK_TTS_FORMAT=wav                    # Output format: wav, mp3
VOICEHELPDESK_TTS_QUALITY=medium                # Quality: low, medium, high
```

### Audio Processing Configuration

```bash
# Audio Input Settings
VOICEHELPDESK_AUDIO_SAMPLE_RATE=16000           # Input sample rate
VOICEHELPDESK_AUDIO_CHANNELS=1                  # Number of audio channels
VOICEHELPDESK_AUDIO_FORMAT=wav                  # Default audio format
VOICEHELPDESK_AUDIO_MAX_DURATION=300            # Max audio duration (seconds)
VOICEHELPDESK_AUDIO_MAX_FILE_SIZE=50MB          # Max audio file size

# Voice Activity Detection
VOICEHELPDESK_VAD_ENABLED=true                  # Enable VAD
VOICEHELPDESK_VAD_THRESHOLD=0.5                 # VAD sensitivity (0.0-1.0)
VOICEHELPDESK_VAD_MIN_SPEECH_DURATION=0.5       # Minimum speech duration (seconds)
VOICEHELPDESK_VAD_MIN_SILENCE_DURATION=1.0      # Minimum silence duration (seconds)

# Noise Reduction
VOICEHELPDESK_NOISE_REDUCTION_ENABLED=true      # Enable noise reduction
VOICEHELPDESK_NOISE_REDUCTION_STRENGTH=0.5      # Noise reduction strength (0.0-1.0)
VOICEHELPDESK_NOISE_REDUCTION_STATIONARY=true   # Assume stationary noise

# Audio Storage
VOICEHELPDESK_AUDIO_STORAGE_PATH=/app/audio     # Audio files storage path
VOICEHELPDESK_AUDIO_RETENTION_DAYS=30           # Audio file retention (days)
VOICEHELPDESK_AUDIO_CLEANUP_ENABLED=true        # Enable automatic cleanup
```

### Celery Configuration

```bash
# Celery Broker
CELERY_BROKER_URL=redis://localhost:6379/0      # Message broker URL
CELERY_RESULT_BACKEND=redis://localhost:6379/0  # Result backend URL
CELERY_TASK_SERIALIZER=json                     # Task serialization format
CELERY_RESULT_SERIALIZER=json                   # Result serialization format
CELERY_ACCEPT_CONTENT=json                      # Accepted content types

# Worker Settings
CELERY_WORKER_CONCURRENCY=4                     # Worker concurrency
CELERY_WORKER_PREFETCH_MULTIPLIER=1             # Task prefetch multiplier
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000          # Max tasks per worker
CELERY_WORKER_TIMEOUT=300                       # Task timeout (seconds)

# Queue Configuration
CELERY_TASK_DEFAULT_QUEUE=celery                # Default queue name
CELERY_TASK_ROUTES={"audio.*": {"queue": "audio"}}  # Task routing

# Beat Scheduler
CELERY_BEAT_SCHEDULE_FILENAME=/tmp/celerybeat-schedule  # Beat schedule file
CELERY_BEAT_MAX_LOOP_INTERVAL=300               # Max loop interval (seconds)
```

### External Services

#### Email Configuration
```bash
# SMTP Settings
VOICEHELPDESK_SMTP_SERVER=smtp.gmail.com        # SMTP server
VOICEHELPDESK_SMTP_PORT=587                     # SMTP port
VOICEHELPDESK_SMTP_USERNAME=your-email@gmail.com # SMTP username
VOICEHELPDESK_SMTP_PASSWORD=your-app-password   # SMTP password
VOICEHELPDESK_SMTP_USE_TLS=true                 # Use TLS encryption
VOICEHELPDESK_SMTP_USE_SSL=false                # Use SSL encryption

# Email Settings
VOICEHELPDESK_EMAIL_FROM=noreply@yourdomain.com # Default sender
VOICEHELPDESK_EMAIL_TIMEOUT=30                  # Email timeout (seconds)
VOICEHELPDESK_EMAIL_MAX_RETRIES=3               # Maximum retry attempts
```

#### Ticketing System Integration
```bash
# Ticketing API
VOICEHELPDESK_TICKETING_API_URL=https://your-ticketing-system.com/api  # Ticketing API URL
VOICEHELPDESK_TICKETING_API_KEY=your-api-key    # API key
VOICEHELPDESK_TICKETING_API_VERSION=v2          # API version
VOICEHELPDESK_TICKETING_TIMEOUT=30              # API timeout (seconds)

# Auto-escalation Settings
VOICEHELPDESK_AUTO_ESCALATION_ENABLED=true      # Enable auto-escalation
VOICEHELPDESK_ESCALATION_CONFIDENCE_THRESHOLD=0.3  # Confidence threshold
VOICEHELPDESK_ESCALATION_DELAY=300              # Escalation delay (seconds)
```

### Monitoring and Observability

#### Prometheus Metrics
```bash
# Metrics Configuration
VOICEHELPDESK_METRICS_ENABLED=true              # Enable metrics collection
VOICEHELPDESK_METRICS_PORT=8001                 # Metrics endpoint port
VOICEHELPDESK_METRICS_PATH=/metrics             # Metrics endpoint path
VOICEHELPDESK_METRICS_INTERVAL=15               # Collection interval (seconds)

# Custom Metrics
VOICEHELPDESK_BUSINESS_METRICS_ENABLED=true     # Enable business metrics
VOICEHELPDESK_PERFORMANCE_METRICS_ENABLED=true  # Enable performance metrics
VOICEHELPDESK_SYSTEM_METRICS_ENABLED=true       # Enable system metrics
```

#### Sentry Error Tracking
```bash
# Sentry Configuration
SENTRY_DSN=https://your-dsn@sentry.io/project   # Sentry DSN
SENTRY_ENVIRONMENT=production                   # Environment name
SENTRY_RELEASE=1.0.0                           # Release version
SENTRY_SAMPLE_RATE=1.0                         # Error sample rate (0.0-1.0)
SENTRY_TRACES_SAMPLE_RATE=0.1                  # Performance sample rate

# Sentry Features
SENTRY_ATTACH_STACKTRACE=true                  # Include stack traces
SENTRY_SEND_DEFAULT_PII=false                 # Send personally identifiable info
SENTRY_MAX_BREADCRUMBS=100                     # Maximum breadcrumbs
```

### Security Configuration

#### Authentication
```bash
# JWT Settings
VOICEHELPDESK_JWT_SECRET_KEY=your-jwt-secret    # JWT signing key
VOICEHELPDESK_JWT_ALGORITHM=HS256               # JWT algorithm
VOICEHELPDESK_JWT_EXPIRATION=3600               # Token expiration (seconds)
VOICEHELPDESK_JWT_REFRESH_EXPIRATION=86400      # Refresh token expiration

# API Keys
VOICEHELPDESK_API_KEY_HEADER=X-API-Key          # API key header name
VOICEHELPDESK_API_KEY_REQUIRED=false            # Require API key for all requests
```

#### Rate Limiting
```bash
# Rate Limiting
VOICEHELPDESK_RATE_LIMIT_ENABLED=true           # Enable rate limiting
VOICEHELPDESK_RATE_LIMIT_PER_MINUTE=60          # Requests per minute
VOICEHELPDESK_RATE_LIMIT_PER_HOUR=1000          # Requests per hour
VOICEHELPDESK_RATE_LIMIT_PER_DAY=10000          # Requests per day

# Rate Limit Storage
VOICEHELPDESK_RATE_LIMIT_STORAGE=redis          # Storage backend: redis, memory
VOICEHELPDESK_RATE_LIMIT_KEY_PREFIX=rl:         # Redis key prefix
```

## Configuration Files

### Main Configuration File
```python
# src/voicehelpdeskai/config/config.py
from pydantic import BaseSettings, Field
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Application Settings
    env: str = Field("development", env="VOICEHELPDESK_ENV")
    debug: bool = Field(False, env="VOICEHELPDESK_DEBUG")
    secret_key: str = Field(..., env="VOICEHELPDESK_SECRET_KEY")
    
    # Server Settings
    host: str = Field("0.0.0.0", env="VOICEHELPDESK_HOST")
    port: int = Field(8000, env="VOICEHELPDESK_PORT")
    workers: int = Field(4, env="VOICEHELPDESK_WORKERS")
    
    # Database Settings
    database_url: str = Field(..., env="VOICEHELPDESK_DATABASE_URL")
    redis_url: str = Field(..., env="VOICEHELPDESK_REDIS_URL")
    
    # AI Settings
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    whisper_model: str = Field("base", env="VOICEHELPDESK_WHISPER_MODEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
```

### Audio Configuration
```yaml
# config/audio.yml
audio:
  input:
    sample_rate: 16000
    channels: 1
    format: "wav"
    max_duration: 300
    max_file_size: "50MB"
  
  processing:
    vad:
      enabled: true
      threshold: 0.5
      min_speech_duration: 0.5
      min_silence_duration: 1.0
    
    noise_reduction:
      enabled: true
      strength: 0.5
      stationary: true
  
  output:
    sample_rate: 22050
    format: "wav"
    quality: "medium"
  
  storage:
    path: "/app/audio"
    retention_days: 30
    cleanup_enabled: true
```

### Model Configuration
```yaml
# config/models.yml
models:
  whisper:
    model: "base"
    device: "auto"
    language: "auto"
    temperature: 0.0
    beam_size: 5
    patience: 1.0
    fp16: true
    batch_size: 1
    max_length: 30
  
  llm:
    provider: "openai"
    model: "gpt-3.5-turbo"
    max_tokens: 150
    temperature: 0.7
    top_p: 1.0
    frequency_penalty: 0.0
    presence_penalty: 0.0
    timeout: 30
    max_retries: 3
  
  piper:
    model: "en_US-amy-medium"
    speaker_id: 0
    speed: 1.0
    noise_scale: 0.667
    length_scale: 1.0
```

### Logging Configuration
```yaml
# config/logging.yml
version: 1
disable_existing_loggers: false

formatters:
  json:
    class: "pythonjsonlogger.jsonlogger.JsonFormatter"
    format: "%(asctime)s %(name)s %(levelname)s %(message)s"
  
  detailed:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s"

handlers:
  console:
    class: "logging.StreamHandler"
    level: "INFO"
    formatter: "detailed"
    stream: "ext://sys.stdout"
  
  file:
    class: "logging.handlers.RotatingFileHandler"
    level: "INFO"
    formatter: "json"
    filename: "/app/logs/app.log"
    maxBytes: 104857600  # 100MB
    backupCount: 5
  
  error_file:
    class: "logging.handlers.RotatingFileHandler"
    level: "ERROR"
    formatter: "json"
    filename: "/app/logs/error.log"
    maxBytes: 52428800  # 50MB
    backupCount: 10

loggers:
  voicehelpdeskai:
    level: "INFO"
    handlers: ["console", "file"]
    propagate: false
  
  "voicehelpdeskai.core.audio":
    level: "DEBUG"
    handlers: ["file"]
    propagate: false

root:
  level: "WARNING"
  handlers: ["console"]
```

## AI Model Configuration

### Whisper Model Selection
```python
# Model size vs. performance trade-offs
WHISPER_MODELS = {
    "tiny": {
        "size": "39 MB",
        "vram": "~1 GB",
        "speed": "~32x realtime",
        "accuracy": "Good for simple speech"
    },
    "base": {
        "size": "74 MB", 
        "vram": "~1 GB",
        "speed": "~16x realtime",
        "accuracy": "Good general purpose"
    },
    "small": {
        "size": "244 MB",
        "vram": "~2 GB", 
        "speed": "~6x realtime",
        "accuracy": "Better accuracy"
    },
    "medium": {
        "size": "769 MB",
        "vram": "~5 GB",
        "speed": "~2x realtime", 
        "accuracy": "High accuracy"
    },
    "large": {
        "size": "1550 MB",
        "vram": "~10 GB",
        "speed": "~1x realtime",
        "accuracy": "Highest accuracy"
    }
}
```

### LLM Provider Configuration
```python
# OpenAI Configuration
OPENAI_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "model": "gpt-3.5-turbo",
    "max_tokens": 150,
    "temperature": 0.7,
    "timeout": 30
}

# Azure OpenAI Configuration
AZURE_OPENAI_CONFIG = {
    "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
    "api_base": os.getenv("AZURE_OPENAI_ENDPOINT"),
    "api_version": "2023-12-01-preview",
    "deployment_name": "gpt-35-turbo",
    "timeout": 30
}

# Anthropic Configuration
ANTHROPIC_CONFIG = {
    "api_key": os.getenv("ANTHROPIC_API_KEY"),
    "model": "claude-3-sonnet-20240229",
    "max_tokens": 150,
    "temperature": 0.7,
    "timeout": 30
}
```

## Database Configuration

### Connection Pool Settings
```python
# SQLAlchemy Configuration
DATABASE_CONFIG = {
    "pool_size": 20,              # Base pool size
    "max_overflow": 30,           # Additional connections
    "pool_timeout": 30,           # Connection wait timeout
    "pool_recycle": 3600,         # Connection refresh interval
    "pool_pre_ping": True,        # Validate connections
    "echo": False,                # Log SQL queries
    "connect_args": {
        "connect_timeout": 10,
        "command_timeout": 30,
        "server_settings": {
            "application_name": "voicehelpdesk",
            "search_path": "public"
        }
    }
}
```

### Redis Configuration
```python
# Redis Configuration
REDIS_CONFIG = {
    "decode_responses": True,
    "health_check_interval": 30,
    "socket_keepalive": True,
    "socket_keepalive_options": {},
    "connection_pool_kwargs": {
        "max_connections": 50,
        "retry_on_timeout": True
    }
}
```

## Performance Tuning

### Application Performance
```bash
# Worker Configuration
VOICEHELPDESK_WORKERS=8                         # CPU cores * 2
VOICEHELPDESK_WORKER_CLASS=uvicorn.workers.UvicornWorker
VOICEHELPDESK_WORKER_CONNECTIONS=1000           # Max connections per worker
VOICEHELPDESK_MAX_REQUESTS=1000                 # Requests before worker restart
VOICEHELPDESK_MAX_REQUESTS_JITTER=100           # Random jitter for restart
VOICEHELPDESK_PRELOAD_APP=true                  # Preload application code

# Memory Management
VOICEHELPDESK_WORKER_MEMORY_LIMIT=2GB           # Worker memory limit
VOICEHELPDESK_GRACEFUL_TIMEOUT=30               # Graceful shutdown timeout
VOICEHELPDESK_KEEPALIVE_TIMEOUT=2               # Keep-alive timeout
```

### Caching Configuration
```bash
# Response Caching
VOICEHELPDESK_CACHE_ENABLED=true                # Enable response caching
VOICEHELPDESK_CACHE_DEFAULT_TTL=300             # Default cache TTL
VOICEHELPDESK_CACHE_MAX_SIZE=1000               # Max cached items
VOICEHELPDESK_CACHE_COMPRESSION=true            # Compress cached data

# Model Caching
VOICEHELPDESK_MODEL_CACHE_ENABLED=true          # Cache model responses
VOICEHELPDESK_MODEL_CACHE_TTL=3600              # Model cache TTL
VOICEHELPDESK_TRANSCRIPTION_CACHE_TTL=7200      # Transcription cache TTL
```

## Environment-Specific Settings

### Development Environment
```bash
# .env.development
VOICEHELPDESK_ENV=development
VOICEHELPDESK_DEBUG=true
VOICEHELPDESK_LOG_LEVEL=DEBUG
VOICEHELPDESK_DATABASE_URL=sqlite:///./data/dev.db
VOICEHELPDESK_REDIS_URL=redis://localhost:6379/0
VOICEHELPDESK_WHISPER_MODEL=tiny
VOICEHELPDESK_CORS_ORIGINS=http://localhost:3000,http://localhost:8080
VOICEHELPDESK_METRICS_ENABLED=false
SENTRY_DSN=
```

### Staging Environment
```bash
# .env.staging
VOICEHELPDESK_ENV=staging
VOICEHELPDESK_DEBUG=false
VOICEHELPDESK_LOG_LEVEL=INFO
VOICEHELPDESK_DATABASE_URL=postgresql://user:pass@staging-db:5432/voicehelpdesk
VOICEHELPDESK_REDIS_URL=redis://staging-redis:6379/0
VOICEHELPDESK_WHISPER_MODEL=base
VOICEHELPDESK_CORS_ORIGINS=https://staging.yourdomain.com
VOICEHELPDESK_METRICS_ENABLED=true
SENTRY_DSN=https://staging-dsn@sentry.io/project
```

### Production Environment
```bash
# .env.production
VOICEHELPDESK_ENV=production
VOICEHELPDESK_DEBUG=false
VOICEHELPDESK_LOG_LEVEL=WARNING
VOICEHELPDESK_DATABASE_URL=postgresql://user:pass@prod-db:5432/voicehelpdesk
VOICEHELPDESK_REDIS_URL=redis://prod-redis:6379/0
VOICEHELPDESK_WHISPER_MODEL=base
VOICEHELPDESK_CORS_ORIGINS=https://app.yourdomain.com
VOICEHELPDESK_METRICS_ENABLED=true
VOICEHELPDESK_RATE_LIMIT_ENABLED=true
SENTRY_DSN=https://prod-dsn@sentry.io/project
```

---

## Configuration Validation

### Environment Validation Script
```python
#!/usr/bin/env python3
# scripts/validate_config.py

import os
import sys
from urllib.parse import urlparse

def validate_config():
    """Validate essential configuration."""
    errors = []
    
    # Required environment variables
    required_vars = [
        "VOICEHELPDESK_SECRET_KEY",
        "VOICEHELPDESK_DATABASE_URL", 
        "VOICEHELPDESK_REDIS_URL",
        "OPENAI_API_KEY"
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")
    
    # Validate URLs
    db_url = os.getenv("VOICEHELPDESK_DATABASE_URL")
    if db_url:
        parsed = urlparse(db_url)
        if not parsed.scheme or not parsed.netloc:
            errors.append("Invalid database URL format")
    
    # Check model files
    model_path = os.getenv("VOICEHELPDESK_MODEL_PATH", "/app/models")
    if not os.path.exists(model_path):
        errors.append(f"Model path does not exist: {model_path}")
    
    if errors:
        print("Configuration validation failed:")
        for error in errors:
            print(f"❌ {error}")
        sys.exit(1)
    else:
        print("✅ Configuration validation passed")

if __name__ == "__main__":
    validate_config()
```

### Runtime Configuration Check
```python
# src/voicehelpdeskai/config/validation.py
from pydantic import validator
from typing import Optional
import os

class Settings(BaseSettings):
    # ... other settings ...
    
    @validator('secret_key')
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError('Secret key must be at least 32 characters long')
        return v
    
    @validator('database_url')
    def validate_database_url(cls, v):
        if not v.startswith(('postgresql://', 'sqlite:///')):
            raise ValueError('Database URL must be PostgreSQL or SQLite')
        return v
    
    @validator('whisper_model')
    def validate_whisper_model(cls, v):
        allowed_models = ['tiny', 'base', 'small', 'medium', 'large']
        if v not in allowed_models:
            raise ValueError(f'Whisper model must be one of: {allowed_models}')
        return v
    
    @validator('workers')
    def validate_workers(cls, v):
        if v < 1 or v > 32:
            raise ValueError('Worker count must be between 1 and 32')
        return v
```

For more information, see:
- [Deployment Guide](deployment.md)
- [Security Configuration](security.md)
- [Performance Tuning](performance.md)
- [Environment Management](environment.md)