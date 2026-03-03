# Troubleshooting Guide

## Table of Contents
1. [Overview](#overview)
2. [Common Issues](#common-issues)
3. [Application Startup Issues](#application-startup-issues)
4. [Audio Processing Problems](#audio-processing-problems)
5. [AI Model Issues](#ai-model-issues)
6. [Database Connection Problems](#database-connection-problems)
7. [Performance Issues](#performance-issues)
8. [WebSocket Problems](#websocket-problems)
9. [Security Issues](#security-issues)
10. [Monitoring and Debugging](#monitoring-and-debugging)

## Overview

This guide provides solutions for common issues encountered when deploying and operating VoiceHelpDeskAI. Each section includes symptoms, diagnosis steps, and resolution procedures.

### Before You Start
1. **Check System Health**: Run `make health` to get overall system status
2. **Review Logs**: Check application and service logs for error messages
3. **Verify Configuration**: Ensure all environment variables are properly set
4. **Check Dependencies**: Verify all required services are running

### Diagnostic Commands Quick Reference
```bash
# System status
make ps                    # Service status
make health               # Health checks
make logs                 # All logs
make logs-app             # Application logs only
make stats                # Resource usage

# Service-specific logs
make logs-celery          # Celery worker logs
make logs-nginx           # Nginx logs
make logs-redis           # Redis logs

# Interactive debugging
make shell-app            # Application container shell
make shell-celery         # Celery container shell
make db-shell             # Redis shell
```

## Common Issues

### Issue: "Service Unavailable" Error

#### Symptoms
- HTTP 503 responses
- Cannot connect to application
- Health check fails

#### Diagnosis
```bash
# Check service status
make ps

# Check application logs
make logs-app | tail -50

# Test health endpoint directly
curl -f http://localhost:8000/health
```

#### Resolution
```bash
# Restart services
make restart

# If database issues
make migrate

# If Redis issues
make db-shell
ping

# Scale up if resource constrained
make scale-app WORKERS=6
```

### Issue: High Memory Usage

#### Symptoms
- Application becoming slow
- Out of Memory errors
- Containers being killed

#### Diagnosis
```bash
# Check memory usage
make stats

# Check application metrics
curl http://localhost:8001/metrics | grep memory

# Check for memory leaks
make logs-app | grep -i "memory\|oom"
```

#### Resolution
```bash
# Restart application
make restart-app

# Increase memory limits (Docker Compose)
# Edit docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 4G

# Scale horizontally
make scale-app WORKERS=4
```

### Issue: Slow Response Times

#### Symptoms
- API responses taking >2 seconds
- Timeouts occurring
- Users reporting slow performance

#### Diagnosis
```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health

# Check Grafana dashboards
make open-grafana

# Check database performance
make logs | grep -i "slow query"
```

#### Resolution
```bash
# Scale application
make scale-app WORKERS=8

# Optimize database
# Connect to database and run:
# ANALYZE;
# REINDEX;

# Clear cache
make shell-app
python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
r.flushdb()
"
```

## Application Startup Issues

### Issue: Application Won't Start

#### Symptoms
- Container exits immediately
- "Failed to start" errors
- Application process crashes on startup

#### Diagnosis
```bash
# Check container logs
docker-compose logs app

# Check environment variables
make shell-app
env | grep VOICEHELPDESK

# Validate configuration
python scripts/validate_config.py
```

#### Common Causes & Solutions

**1. Missing Environment Variables**
```bash
# Check .env file exists
ls -la .env

# Copy from template if missing
cp .env.example .env

# Edit required variables
nano .env
```

**2. Database Connection Issues**
```bash
# Test database connectivity
make shell-app
python -c "
from voicehelpdeskai.config import config_manager
from sqlalchemy import create_engine
engine = create_engine(config_manager.get('VOICEHELPDESK_DATABASE_URL'))
print('Database connection successful')
"
```

**3. Model Loading Issues**
```bash
# Check model files exist
make shell-app
ls -la /app/models/

# Download missing models
python scripts/download_models.py
```

**4. Port Already in Use**
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Kill the process or change port
export VOICEHELPDESK_PORT=8001
```

### Issue: Import Errors

#### Symptoms
- "ModuleNotFoundError" errors
- "ImportError" messages
- Python path issues

#### Resolution
```bash
# Rebuild containers
make build-no-cache

# Check Python path
make shell-app
python -c "import sys; print('\n'.join(sys.path))"

# Install missing dependencies
pip install -r requirements/base.txt
```

## Audio Processing Problems

### Issue: Audio Upload Fails

#### Symptoms
- "Invalid audio format" errors
- Upload timeouts
- Audio processing errors

#### Diagnosis
```bash
# Check supported formats
make shell-app
python -c "
import soundfile as sf
print('Supported formats:', sf.available_formats())
"

# Check file size limits
curl -F "audio=@large_file.wav" http://localhost:8000/audio/transcribe
```

#### Resolution
```bash
# Increase file size limits
# Edit nginx.conf:
# client_max_body_size 100M;

# Check audio file format
file audio.wav
ffprobe audio.wav

# Convert to supported format
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
```

### Issue: Poor Transcription Quality

#### Symptoms
- Incorrect transcriptions
- Low confidence scores
- Missing words or phrases

#### Diagnosis
```bash
# Check audio quality metrics
make logs-app | grep "audio_quality"

# Test with known good audio
curl -F "audio=@test_audio.wav" http://localhost:8000/audio/transcribe
```

#### Resolution
```bash
# Improve audio preprocessing
# Edit .env:
VOICEHELPDESK_NOISE_REDUCTION_ENABLED=true
VOICEHELPDESK_VAD_ENABLED=true

# Use larger Whisper model
VOICEHELPDESK_WHISPER_MODEL=small

# Restart to apply changes
make restart
```

### Issue: Audio Processing Timeouts

#### Symptoms
- 504 Gateway Timeout errors
- Long processing times
- Audio tasks stuck

#### Resolution
```bash
# Increase timeout limits
# Edit nginx.conf:
# proxy_read_timeout 300s;

# Scale Celery workers
make scale-celery WORKERS=8

# Check Celery queue status
make open-flower
```

## AI Model Issues

### Issue: OpenAI API Errors

#### Symptoms
- "Invalid API key" errors
- Rate limit exceeded
- Connection timeouts

#### Diagnosis
```bash
# Test API key
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Check rate limits
make logs-app | grep -i "rate limit"
```

#### Resolution
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Set in environment
export OPENAI_API_KEY=your-key-here

# Implement retry logic and backoff
# Edit .env:
VOICEHELPDESK_LLM_MAX_RETRIES=5
VOICEHELPDESK_LLM_BACKOFF_FACTOR=2
```

### Issue: Whisper Model Loading Fails

#### Symptoms
- "Model not found" errors
- CUDA out of memory
- Slow model loading

#### Diagnosis
```bash
# Check available models
make shell-app
python -c "
import whisper
print('Available models:', whisper.available_models())
"

# Check GPU memory
nvidia-smi

# Check model files
ls -la /app/models/whisper/
```

#### Resolution
```bash
# Use smaller model
VOICEHELPDESK_WHISPER_MODEL=tiny

# Force CPU usage
VOICEHELPDESK_WHISPER_DEVICE=cpu

# Download models manually
make shell-app
python -c "
import whisper
model = whisper.load_model('base')
print('Model loaded successfully')
"
```

### Issue: High Model Inference Latency

#### Symptoms
- Slow AI responses
- Timeouts on model calls
- High CPU/GPU usage

#### Resolution
```bash
# Enable model caching
VOICEHELPDESK_MODEL_CACHE_ENABLED=true

# Use GPU if available
VOICEHELPDESK_WHISPER_DEVICE=cuda
VOICEHELPDESK_WHISPER_FP16=true

# Optimize batch processing
VOICEHELPDESK_WHISPER_BATCH_SIZE=4

# Scale model workers
make scale-celery WORKERS=12
```

## Database Connection Problems

### Issue: Database Connection Refused

#### Symptoms
- "Connection refused" errors
- Cannot connect to PostgreSQL/SQLite
- Database timeouts

#### Diagnosis
```bash
# Check database container
docker-compose ps postgres

# Test connection
make shell-app
python -c "
import psycopg2
conn = psycopg2.connect('postgresql://user:pass@postgres:5432/db')
print('Connected successfully')
"
```

#### Resolution
```bash
# Restart database service
docker-compose restart postgres

# Check database logs
make logs | grep postgres

# Verify credentials
echo $VOICEHELPDESK_DATABASE_URL

# For SQLite, check file permissions
ls -la data/app.db
```

### Issue: Database Migration Fails

#### Symptoms
- Alembic errors
- Schema version conflicts
- Migration timeout

#### Diagnosis
```bash
# Check current migration status
make shell-app
alembic current

# Check migration history
alembic history
```

#### Resolution
```bash
# Reset to latest migration
make shell-app
alembic stamp head

# Run migrations manually
alembic upgrade head

# If migrations are corrupted, recreate
alembic downgrade base
alembic upgrade head
```

### Issue: Database Performance Issues

#### Symptoms
- Slow queries
- High database CPU
- Connection pool exhaustion

#### Diagnosis
```bash
# Check slow queries (PostgreSQL)
make db-shell
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;

# Check connection count
SELECT count(*) FROM pg_stat_activity;
```

#### Resolution
```bash
# Increase connection pool
VOICEHELPDESK_DB_POOL_SIZE=30
VOICEHELPDESK_DB_MAX_OVERFLOW=50

# Add indexes for slow queries
# Connect to database and analyze query plans
EXPLAIN ANALYZE SELECT * FROM conversations WHERE user_id = 'user123';

# Run database maintenance
VACUUM ANALYZE;
REINDEX;
```

## Performance Issues

### Issue: High CPU Usage

#### Symptoms
- CPU usage >90%
- Application slowdown
- Response timeouts

#### Diagnosis
```bash
# Check CPU usage by service
make stats

# Check application profiling
make logs-app | grep "cpu_usage"

# Monitor real-time usage
htop
```

#### Resolution
```bash
# Scale application horizontally
make scale-app WORKERS=8

# Optimize worker configuration
VOICEHELPDESK_WORKER_CONCURRENCY=2
VOICEHELPDESK_WORKER_PREFETCH_MULTIPLIER=1

# Use CPU-optimized settings
VOICEHELPDESK_WHISPER_DEVICE=cpu
VOICEHELPDESK_WHISPER_FP16=false
```

### Issue: Memory Leaks

#### Symptoms
- Continuously increasing memory usage
- Out of memory errors
- Garbage collection issues

#### Diagnosis
```bash
# Monitor memory usage over time
watch -n 5 'make stats'

# Check for memory leaks in logs
make logs-app | grep -i "memory\|leak\|gc"

# Profile memory usage
make shell-app
python -m memory_profiler your_script.py
```

#### Resolution
```bash
# Restart workers periodically
CELERY_WORKER_MAX_TASKS_PER_CHILD=500

# Enable garbage collection monitoring
VOICEHELPDESK_GC_DEBUG=true

# Limit worker memory
VOICEHELPDESK_WORKER_MEMORY_LIMIT=2GB

# Clear caches periodically
# Add to cron:
# 0 */4 * * * docker-compose exec redis redis-cli FLUSHDB
```

### Issue: Disk Space Issues

#### Symptoms
- "No space left on device"
- Log files growing too large
- Temporary files not cleaned

#### Diagnosis
```bash
# Check disk usage
df -h

# Check largest files
du -h / | sort -hr | head -20

# Check Docker usage
docker system df
```

#### Resolution
```bash
# Clean up Docker resources
docker system prune -a

# Rotate logs manually
make logs-app > /dev/null
truncate -s 0 logs/*.log

# Setup log rotation
# Add to crontab:
# 0 2 * * * find /app/logs -name "*.log" -mtime +7 -delete

# Enable automatic cleanup
VOICEHELPDESK_AUDIO_CLEANUP_ENABLED=true
VOICEHELPDESK_AUDIO_RETENTION_DAYS=7
```

## WebSocket Problems

### Issue: WebSocket Connection Fails

#### Symptoms
- WebSocket handshake fails
- Connection immediately closes
- "WebSocket connection error"

#### Diagnosis
```bash
# Test WebSocket connection
wscat -c ws://localhost:8000/ws/audio/test-session

# Check nginx WebSocket configuration
make shell-nginx
cat /etc/nginx/nginx.conf | grep -A 10 -B 10 websocket
```

#### Resolution
```bash
# Fix nginx WebSocket proxy
# Edit nginx.conf:
location /ws/ {
    proxy_pass http://app:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}

# Restart nginx
docker-compose restart nginx
```

### Issue: Audio Streaming Interruptions

#### Symptoms
- Audio chunks lost
- Streaming stops unexpectedly
- Buffer overflow errors

#### Diagnosis
```bash
# Check WebSocket logs
make logs-app | grep -i websocket

# Monitor connection stability
# Use browser developer tools Network tab
```

#### Resolution
```bash
# Increase buffer sizes
VOICEHELPDESK_AUDIO_BUFFER_SIZE=8192
VOICEHELPDESK_WEBSOCKET_TIMEOUT=60

# Optimize audio chunking
VOICEHELPDESK_AUDIO_CHUNK_SIZE=1024

# Enable connection keepalive
VOICEHELPDESK_WEBSOCKET_KEEPALIVE=true
```

## Security Issues

### Issue: Authentication Failures

#### Symptoms
- 401 Unauthorized errors
- JWT token errors
- API key validation fails

#### Diagnosis
```bash
# Test authentication
curl -H "Authorization: Bearer invalid-token" \
     http://localhost:8000/conversations

# Check JWT configuration
echo $VOICEHELPDESK_JWT_SECRET_KEY | wc -c
```

#### Resolution
```bash
# Generate new JWT secret
VOICEHELPDESK_JWT_SECRET_KEY=$(openssl rand -hex 32)

# Check token expiration
VOICEHELPDESK_JWT_EXPIRATION=3600

# Verify API key format
curl -H "X-API-Key: your-api-key" \
     http://localhost:8000/health
```

### Issue: CORS Errors

#### Symptoms
- "CORS policy" errors in browser
- Cross-origin requests blocked
- Preflight failures

#### Diagnosis
```bash
# Test CORS headers
curl -H "Origin: https://yourdomain.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     http://localhost:8000/conversations
```

#### Resolution
```bash
# Configure CORS origins
VOICEHELPDESK_CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Allow all origins (development only)
VOICEHELPDESK_CORS_ORIGINS=*

# Configure allowed methods
VOICEHELPDESK_CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS
```

### Issue: Rate Limiting Problems

#### Symptoms
- 429 Too Many Requests
- Rate limit headers missing
- Legitimate users blocked

#### Diagnosis
```bash
# Check rate limit status
curl -v http://localhost:8000/health | grep -i rate

# Check Redis rate limit keys
make db-shell
KEYS rl:*
```

#### Resolution
```bash
# Adjust rate limits
VOICEHELPDESK_RATE_LIMIT_PER_MINUTE=120
VOICEHELPDESK_RATE_LIMIT_PER_HOUR=2000

# Clear rate limit data
make db-shell
DEL rl:192.168.1.100

# Disable rate limiting temporarily
VOICEHELPDESK_RATE_LIMIT_ENABLED=false
```

## Monitoring and Debugging

### Debug Mode Setup

```bash
# Enable debug mode
export VOICEHELPDESK_DEBUG=true
export VOICEHELPDESK_LOG_LEVEL=DEBUG

# Start with debug logging
make down
make up

# Monitor debug logs
make logs-app | grep DEBUG
```

### Performance Profiling

```bash
# Enable application profiling
make shell-app
pip install py-spy

# Profile running application
py-spy top --pid $(pgrep -f uvicorn)

# Generate flame graph
py-spy record -o profile.svg --pid $(pgrep -f uvicorn)
```

### Database Debugging

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Check slow queries
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check table sizes
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Network Debugging

```bash
# Test internal connectivity
make shell-app
ping redis
ping postgres

# Check DNS resolution
nslookup redis
nslookup postgres

# Test service ports
telnet redis 6379
telnet postgres 5432
```

### Log Analysis

```bash
# Search for specific errors
make logs-app | grep -i "error\|exception\|failed"

# Monitor real-time errors
make logs-app -f | grep -i error

# Analyze error patterns
make logs-app | grep error | awk '{print $4}' | sort | uniq -c

# Check for memory issues
make logs-app | grep -i "memory\|oom\|killed"
```

---

## Emergency Procedures

### Service Down Emergency

```bash
# 1. Quick health check
make health

# 2. Restart all services
make restart

# 3. Check for recent changes
git log --oneline -10

# 4. Rollback if needed
git checkout HEAD~1
make down
make up-build

# 5. Scale up resources
make scale-app WORKERS=8
make scale-celery WORKERS=12
```

### Data Corruption Emergency

```bash
# 1. Stop all services immediately
make down

# 2. Backup current state
cp -r data/ data_backup_$(date +%Y%m%d_%H%M%S)

# 3. Restore from latest backup
make restore

# 4. Verify data integrity
make shell-app
python scripts/verify_data_integrity.py

# 5. Restart services
make up
```

### Performance Emergency

```bash
# 1. Scale up immediately
make scale-app WORKERS=12
make scale-celery WORKERS=16

# 2. Clear caches
make shell-app
python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
r.flushdb()
print('Cache cleared')
"

# 3. Restart services
make restart

# 4. Monitor metrics
make open-grafana
```

For immediate assistance during emergencies:
- Check [Operations Runbook](../monitoring/runbook.md)
- Contact on-call engineer: [Emergency Contacts](../monitoring/runbook.md#contact-information)
- Review [System Health Dashboard](http://localhost:3000/grafana/d/voicehelpdesk-overview)