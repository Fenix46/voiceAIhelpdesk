# Multi-stage Dockerfile for VoiceHelpDeskAI
# Optimized for production deployment with security hardening

ARG PYTHON_VERSION=3.11
ARG DEBIAN_VERSION=bookworm-slim
ARG NODE_VERSION=18

# =============================================================================
# Base Stage - Common base for all stages
# =============================================================================
FROM python:${PYTHON_VERSION}-${DEBIAN_VERSION} as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    build-essential \
    ffmpeg \
    libsndfile1 \
    libasound2-dev \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# =============================================================================
# Dependencies Builder Stage
# =============================================================================
FROM base as dependencies-builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    cmake \
    pkg-config \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements
COPY requirements/ /tmp/requirements/

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements/prod.txt

# Install additional audio processing libraries
RUN pip install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cpu \
    librosa \
    noisereduce \
    webrtcvad

# =============================================================================
# Model Download Stage
# =============================================================================
FROM base as model-downloader

# Install git-lfs for large model files
RUN apt-get update && apt-get install -y --no-install-recommends \
    git-lfs \
    && rm -rf /var/lib/apt/lists/*

# Create models directory
RUN mkdir -p /app/models && chown -R appuser:appuser /app/models

USER appuser
WORKDIR /app/models

# Download Whisper models
RUN mkdir -p whisper && \
    wget -O whisper/base.pt https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt && \
    wget -O whisper/small.pt https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt

# Download Piper TTS models
RUN mkdir -p piper && \
    wget -O piper/en_US-amy-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx && \
    wget -O piper/en_US-amy-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json

# Download NLU models
RUN mkdir -p nlu && \
    wget -O nlu/intent_classifier.pkl https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.6.0/en_core_web_sm-3.6.0-py3-none-any.whl

# Set proper permissions
USER root
RUN chown -R appuser:appuser /app/models
USER appuser

# =============================================================================
# Frontend Builder Stage
# =============================================================================
FROM node:${NODE_VERSION}-alpine as frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy source code
COPY frontend/ ./

# Build frontend
RUN npm run build

# =============================================================================
# Assets Compilation Stage
# =============================================================================
FROM base as assets-compiler

# Copy virtual environment from dependencies stage
COPY --from=dependencies-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
WORKDIR /app
COPY src/ ./src/
COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Install application in development mode for asset compilation
RUN pip install -e .

# Compile static assets and run any preprocessing
RUN python -c "
import sys
sys.path.insert(0, '/app/src')
from voicehelpdeskai.config import config_manager
print('Configuration validated successfully')
"

# Generate OpenAPI schema
RUN python -c "
from voicehelpdeskai.api.main import app
import json
with open('/app/openapi.json', 'w') as f:
    json.dump(app.openapi(), f)
"

# =============================================================================
# Runtime Stage - Final production image
# =============================================================================
FROM python:${PYTHON_VERSION}-${DEBIAN_VERSION} as runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libasound2 \
    portaudio19-dev \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Copy virtual environment
COPY --from=dependencies-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application directories
RUN mkdir -p /app/src /app/logs /app/data /app/models /app/static && \
    chown -R appuser:appuser /app

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser pyproject.toml alembic.ini ./
COPY --chown=appuser:appuser alembic/ ./alembic/

# Copy models from model-downloader stage
COPY --from=model-downloader --chown=appuser:appuser /app/models ./models/

# Copy frontend build
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist ./static/

# Copy compiled assets
COPY --from=assets-compiler --chown=appuser:appuser /app/openapi.json ./

# Install application in production mode
RUN pip install --no-deps -e .

# Security hardening
RUN chmod -R 755 /app && \
    chmod -R 644 /app/src && \
    find /app -type d -exec chmod 755 {} \; && \
    find /app -name "*.py" -exec chmod 644 {} \;

# Remove unnecessary packages and clean up
RUN apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache \
    && rm -rf /tmp/*

# Switch to non-root user
USER appuser

# Set environment variables for production
ENV PYTHONPATH="/app/src" \
    VOICEHELPDESK_ENV=production \
    VOICEHELPDESK_LOG_LEVEL=INFO \
    VOICEHELPDESK_MODEL_PATH="/app/models" \
    VOICEHELPDESK_STATIC_PATH="/app/static"

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command
CMD ["uvicorn", "voicehelpdeskai.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# =============================================================================
# Development Stage (optional)
# =============================================================================
FROM dependencies-builder as development

# Install development dependencies
RUN pip install --no-cache-dir -r /tmp/requirements/dev.txt

# Install additional development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    htop \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser . .

# Install application in development mode
RUN pip install -e .

USER appuser

# Development environment variables
ENV PYTHONPATH="/app/src" \
    VOICEHELPDESK_ENV=development \
    VOICEHELPDESK_LOG_LEVEL=DEBUG \
    VOICEHELPDESK_RELOAD=true

# Development command with hot reload
CMD ["uvicorn", "voicehelpdeskai.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]