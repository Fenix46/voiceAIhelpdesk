# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Development Commands

### Setup and Installation
```bash
# Complete development setup
make setup-dev              # Creates directories, installs deps, copies .env.example

# Install dependencies only
make install-dev             # Install with dev dependencies
make install-prod            # Production dependencies only
```

### Running the Application
```bash
# Development mode (with auto-reload)
make dev                     # uvicorn with --reload
make run                     # Production mode

# Background services (run in separate terminals)
make celery-worker           # Background task processing
make celery-beat             # Scheduled tasks
make celery-flower           # Task monitoring at :5555
```

### Testing and Quality
```bash
# Testing
make test                    # Run all tests
make test-unit               # Unit tests only
make test-integration        # Integration tests only
make test-cov                # Tests with coverage report

# Code Quality
make lint                    # Run flake8, mypy, bandit
make format                  # Black + isort formatting
make type-check              # MyPy type checking only
make security                # Bandit security scan + safety check
```

### Database Operations
```bash
make migrate                 # Apply migrations (alembic upgrade head)
make create-migration        # Create new migration (interactive)
make reset-db                # Delete and recreate database
```

### Docker Operations
```bash
make docker-build            # Build all images
make docker-run              # Start all services
make docker-down             # Stop all containers
make docker-logs             # View container logs
```

## Architecture Overview

### Core Application Structure
- **FastAPI Application**: Main app in `src/voicehelpdeskai/main.py`
- **Configuration System**: Modern Pydantic-based config in `src/voicehelpdeskai/config/`
  - Legacy config in `core/config.py` is deprecated, redirects to new system
- **API Layer**: RESTful endpoints in `src/voicehelpdeskai/api/`
- **Audio Processing**: Real-time audio handling in `src/voicehelpdeskai/core/audio/`

### Key Components
- **WebSocket Support**: Real-time voice streaming via WebSocket endpoints
- **Background Tasks**: Celery integration for async audio processing
- **Audio Pipeline**: 
  - Voice Activity Detection (VAD)
  - Noise reduction capabilities
  - Multiple format support (wav, mp3, m4a, ogg, flac)
- **AI Integration**: OpenAI API integration for speech recognition and LLM responses

### Database
- **Primary**: SQLite for development (configurable to PostgreSQL)
- **Migrations**: Alembic for schema management
- **Models**: SQLAlchemy ORM models in `src/voicehelpdeskai/models/`

### Caching & Background Jobs
- **Redis**: Session storage, caching, and Celery message broker
- **Celery**: Background task processing for audio operations

## Configuration Management

### Environment Setup
- Copy `.env.example` to `.env` and configure
- Configuration is centralized in `src/voicehelpdeskai/config/config.py`
- Settings are grouped by domain (database, audio, API, logging, etc.)

### Key Configuration Sections
- **AudioSettings**: Sample rates, noise reduction, file paths
- **AIModelSettings**: Model paths, quantization, token limits
- **RedisSettings**: Connection pooling, TTL settings
- **APISettings**: CORS, rate limiting, security

## Development Workflow

### Code Standards
- **Formatting**: Black (line length 88) + isort
- **Type Checking**: MyPy with strict settings
- **Linting**: flake8 + bandit for security
- **Testing**: pytest with asyncio support

### Testing Structure
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Coverage reporting with HTML output
- Pytest markers: `slow`, `integration`, `unit`

### Pre-commit Hooks
- Automatic code formatting and linting
- Security checks before commits
- Install with: `make install-dev` (includes pre-commit setup)

## Audio Processing Notes

### Supported Formats
- Input: wav, mp3, m4a, ogg, flac
- Processing: 16kHz sample rate default
- Real-time streaming via WebSocket

### Audio Pipeline Features
- Circular buffer for streaming audio
- Voice Activity Detection (VAD)
- Noise reduction (when noisereduce available)
- Automatic gain control and normalization

### Dependencies
- **Core Audio**: soundfile, librosa, pyaudio, pydub
- **AI Models**: torch, transformers, openai
- **Optional**: noisereduce (graceful degradation if unavailable)

## Monitoring and Debugging

### Health Checks
- Main health endpoint: `GET /health`
- Application status and version info

### Logging
- Structured JSON logging with Loguru
- Log levels configurable per component
- Sensitive field masking for security

### Monitoring Tools
- Flower for Celery task monitoring (port 5555)
- FastAPI docs at `/docs` and `/redoc`
- Prometheus metrics available (when enabled)

## Important File Locations

### Configuration
- `pyproject.toml`: Project dependencies and tool configuration
- `Makefile`: All development commands
- `docker-compose.yml`: Multi-service development environment
- `alembic.ini`: Database migration settings

### Application Entry Points
- `src/voicehelpdeskai/main.py`: FastAPI application factory
- `src/voicehelpdeskai/api/router.py`: Main API router
- `src/voicehelpdeskai/core/celery.py`: Background task configuration

### Environment Files
- `.env.example`: Template for environment variables
- `requirements/`: Separated requirement files for base/dev/prod