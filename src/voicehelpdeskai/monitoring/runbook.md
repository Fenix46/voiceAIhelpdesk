# VoiceHelpDeskAI Operations Runbook

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [System Architecture](#system-architecture)
3. [Monitoring & Alerting](#monitoring--alerting)
4. [Alert Response Procedures](#alert-response-procedures)
5. [Troubleshooting Guides](#troubleshooting-guides)
6. [Maintenance Procedures](#maintenance-procedures)
7. [Emergency Procedures](#emergency-procedures)
8. [Performance Optimization](#performance-optimization)
9. [Security Incidents](#security-incidents)
10. [Deployment & Rollback](#deployment--rollback)

## Quick Reference

### Key Metrics Dashboard URLs
- **System Overview**: http://localhost:3000/grafana/d/voicehelpdesk-overview
- **API Performance**: http://localhost:3000/grafana/d/voicehelpdesk-api
- **AI Models**: http://localhost:3000/grafana/d/voicehelpdesk-ai
- **Business Metrics**: http://localhost:3000/grafana/d/voicehelpdesk-business
- **Infrastructure**: http://localhost:3000/grafana/d/voicehelpdesk-infrastructure

### Critical Service Endpoints
- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (port 8001)
- **API Documentation**: `GET /docs`
- **Flower (Celery)**: http://localhost:5555
- **Prometheus**: http://localhost:9090

### Emergency Contacts
- **On-Call Engineer**: [Insert contact info]
- **DevOps Team**: [Insert contact info]
- **Product Owner**: [Insert contact info]

### Quick Commands
```bash
# Check service status
make ps

# View logs
make logs-app
make logs-celery

# Restart services
make restart-app
make restart

# Scale services
make scale-app WORKERS=4
make scale-celery WORKERS=6

# Health check
make health

# Access shells
make shell-app
make shell-celery
```

## System Architecture

### Core Components
1. **FastAPI Application** (Main API server)
2. **Celery Workers** (Background task processing)
3. **Redis** (Message broker & caching)
4. **AI Models** (Whisper, Piper, OpenAI)
5. **Database** (SQLite/PostgreSQL)
6. **Nginx** (Reverse proxy & load balancer)

### Data Flow
```
User Request → Nginx → FastAPI → Business Logic
                               ↓
                         Audio Processing → AI Models
                               ↓
                         Celery Tasks → Redis Queue
                               ↓
                         Database Storage
```

### Dependencies
- **External APIs**: OpenAI API, Ticketing System API
- **Storage**: Local file system, Redis persistence
- **Monitoring**: Prometheus, Grafana, Sentry

## Monitoring & Alerting

### Alert Severity Levels

#### CRITICAL (Immediate Response Required)
- **Response Time**: < 15 minutes
- **Escalation**: After 30 minutes
- **Examples**: 
  - High error rate (>5%)
  - System down
  - Security incidents
  - Model inference failures

#### HIGH (Response Required)
- **Response Time**: < 1 hour
- **Escalation**: After 2 hours
- **Examples**:
  - High API latency (>2s)
  - High memory usage (>90%)
  - Queue backlog

#### MEDIUM (Business Hours Response)
- **Response Time**: < 4 hours (business hours)
- **Examples**:
  - Queue backlog warning
  - Low user satisfaction

#### LOW (Informational)
- **Response Time**: Next business day
- **Examples**:
  - Performance degradation warnings

### Key Metrics to Monitor

#### System Health
- **Uptime**: Target 99.9%
- **Response Time**: <1s p95
- **Error Rate**: <1%
- **Memory Usage**: <80%
- **CPU Usage**: <70%

#### Business Metrics
- **Conversation Success Rate**: >85%
- **User Satisfaction**: >4.0/5.0
- **Average Resolution Time**: <2 minutes

#### AI Model Performance
- **Inference Time**: <5s for STT, <10s for LLM
- **Model Accuracy**: >90% for STT
- **Model Availability**: 99.5%

## Alert Response Procedures

### High API Latency Alert

**Alert**: `high_api_latency`
**Threshold**: API response time > 2 seconds for 2 minutes

#### Investigation Steps
1. **Check Grafana Dashboard**: API Performance
2. **Identify Slow Endpoints**: 
   ```bash
   # Check application logs
   make logs-app | grep "duration_ms"
   ```
3. **Check System Resources**:
   ```bash
   # Memory and CPU usage
   make stats
   ```
4. **Check Database Performance**:
   ```bash
   # Redis info
   make db-info
   ```

#### Resolution Actions
1. **Scale Application** (if resource constrained):
   ```bash
   make scale-app WORKERS=6
   ```
2. **Restart Services** (if memory leak suspected):
   ```bash
   make restart-app
   ```
3. **Check AI Model Performance**:
   ```bash
   # Check model inference times in logs
   make logs-app | grep "model_inference"
   ```

### High Error Rate Alert

**Alert**: `high_error_rate`
**Threshold**: HTTP 5xx errors > 5% for 5 minutes

#### Investigation Steps
1. **Check Error Distribution**:
   ```bash
   # View recent errors
   make logs-app | grep "ERROR"
   ```
2. **Check External Dependencies**:
   ```bash
   # Test OpenAI API connectivity
   curl -H "Authorization: Bearer $OPENAI_API_KEY" \
        https://api.openai.com/v1/models
   ```
3. **Review Sentry Dashboard** for error details

#### Resolution Actions
1. **Identify Root Cause** from error logs
2. **Rollback Deployment** if recent changes:
   ```bash
   # Rollback to previous version
   make down
   # Deploy previous version
   make up-build
   ```
3. **Scale Resources** if capacity issue:
   ```bash
   make scale-app WORKERS=8
   ```

### Model Inference Failures Alert

**Alert**: `model_inference_failures`
**Threshold**: >10 model failures in 5 minutes

#### Investigation Steps
1. **Check Model Health**:
   ```bash
   # Run health checks
   make health
   ```
2. **Check GPU Resources** (if applicable):
   ```bash
   # Check GPU memory
   make shell-app
   nvidia-smi
   ```
3. **Check Model Files**:
   ```bash
   # Verify model files exist
   ls -la /app/models/
   ```

#### Resolution Actions
1. **Restart Application**:
   ```bash
   make restart-app
   ```
2. **Check Model Configuration** in environment variables
3. **Switch to Backup Model** if available

### Queue Backlog Alert

**Alert**: `queue_backlog`
**Threshold**: Queue depth > 100 for 10 minutes

#### Investigation Steps
1. **Check Queue Status**:
   ```bash
   # Redis queue lengths
   make db-shell
   LLEN celery
   LLEN audio
   LLEN ai
   ```
2. **Check Worker Status**:
   ```bash
   # Celery worker logs
   make logs-celery
   ```

#### Resolution Actions
1. **Scale Celery Workers**:
   ```bash
   make scale-celery WORKERS=8
   ```
2. **Check for Stuck Tasks**:
   ```bash
   # Access Flower dashboard
   make open-flower
   ```
3. **Purge Failed Tasks** if necessary:
   ```bash
   make shell-app
   celery -A voicehelpdeskai.core.celery purge -f
   ```

## Troubleshooting Guides

### Application Won't Start

#### Symptoms
- Container exits immediately
- Health check fails
- Cannot connect to service

#### Diagnosis
```bash
# Check container logs
make logs-app

# Check configuration
make config

# Verify environment variables
make shell-app
env | grep VOICEHELPDESK
```

#### Common Causes & Solutions
1. **Missing Environment Variables**:
   ```bash
   # Copy and edit .env file
   cp .env.example .env
   # Edit required variables
   ```

2. **Database Connection Issues**:
   ```bash
   # Check database file exists
   ls -la data/
   # Run migrations
   make migrate
   ```

3. **Redis Connection Issues**:
   ```bash
   # Test Redis connectivity
   make db-shell
   ping
   ```

### High Memory Usage

#### Investigation
```bash
# Check memory distribution
make stats

# Check application memory
make shell-app
top -p $(pgrep -f "uvicorn")

# Check for memory leaks
make logs-app | grep "memory"
```

#### Solutions
1. **Restart Application**:
   ```bash
   make restart-app
   ```
2. **Scale Horizontally**:
   ```bash
   make scale-app WORKERS=4
   ```
3. **Tune Model Settings** in configuration

### Audio Processing Issues

#### Symptoms
- Long processing times
- Audio quality degradation
- Transcription accuracy issues

#### Diagnosis
```bash
# Check audio processing logs
make logs-app | grep "audio_processing"

# Check model performance
make logs-app | grep "model_inference"

# Check audio metrics in Grafana
# Dashboard: Audio Processing
```

#### Solutions
1. **Check Audio Format Support**
2. **Verify Noise Reduction Settings**
3. **Check Model Configuration**:
   ```bash
   # Verify model files
   make shell-app
   ls -la /app/models/whisper/
   ```

### WebSocket Connection Issues

#### Symptoms
- Connections dropping
- Audio streaming interruptions
- Real-time features not working

#### Diagnosis
```bash
# Check WebSocket connections
curl -H "Upgrade: websocket" \
     -H "Connection: Upgrade" \
     http://localhost/ws/audio

# Check Nginx configuration
make shell-nginx
cat /etc/nginx/nginx.conf
```

#### Solutions
1. **Check Nginx WebSocket Proxy Configuration**
2. **Verify Network Connectivity**
3. **Check Application WebSocket Handler**

## Maintenance Procedures

### Regular Maintenance Tasks

#### Daily
- [ ] Check system health dashboard
- [ ] Review error logs for anomalies
- [ ] Verify backup completion
- [ ] Check disk space usage

#### Weekly
- [ ] Review performance trends
- [ ] Update security patches
- [ ] Clean up old log files
- [ ] Review user satisfaction metrics

#### Monthly
- [ ] Update dependencies
- [ ] Review and update alert thresholds
- [ ] Capacity planning review
- [ ] Security audit

### Backup Procedures

#### Database Backup
```bash
# Create backup
make backup

# Verify backup
ls -la backups/

# Test restore (in staging)
make restore BACKUP_DATE=20231201_120000
```

#### Configuration Backup
```bash
# Backup configuration files
tar -czf config-backup-$(date +%Y%m%d).tar.gz \
    .env config/ grafana/ prometheus/
```

### Log Rotation

#### Configure Log Rotation
```bash
# Application logs are auto-rotated by Loguru
# System logs rotation
sudo logrotate -f /etc/logrotate.d/voicehelpdesk
```

#### Manual Log Cleanup
```bash
# Clean old logs (older than 30 days)
find logs/ -name "*.log.*" -mtime +30 -delete
```

## Emergency Procedures

### System Down Emergency

#### Immediate Actions (0-5 minutes)
1. **Verify Outage Scope**:
   ```bash
   # Check service status
   make ps
   # Check health endpoint
   curl http://localhost/health
   ```

2. **Check Infrastructure**:
   ```bash
   # Check Docker daemon
   docker info
   # Check disk space
   df -h
   ```

3. **Attempt Quick Recovery**:
   ```bash
   # Restart all services
   make restart
   ```

#### Investigation Phase (5-15 minutes)
1. **Check Recent Changes**:
   ```bash
   # Check deployment history
   git log --oneline -10
   # Check Docker image tags
   docker images | grep voicehelpdesk
   ```

2. **Analyze Logs**:
   ```bash
   # Check all service logs
   make logs
   # Check system logs
   sudo journalctl -u docker -n 50
   ```

#### Recovery Actions (15+ minutes)
1. **Rollback if Deployment Issue**:
   ```bash
   # Rollback to last known good version
   git checkout <previous-commit>
   make down
   make up-build
   ```

2. **Scale Up Resources**:
   ```bash
   # Increase resources
   make scale-app WORKERS=6
   make scale-celery WORKERS=8
   ```

### Data Corruption Emergency

#### Immediate Actions
1. **Stop All Services**:
   ```bash
   make down
   ```

2. **Assess Damage**:
   ```bash
   # Check database integrity
   sqlite3 data/app.db ".schema"
   # Check Redis data
   make db-info
   ```

3. **Restore from Backup**:
   ```bash
   # Restore latest backup
   make restore
   ```

### Security Incident Response

#### Immediate Actions (0-10 minutes)
1. **Isolate Affected Systems**:
   ```bash
   # Stop external access
   docker-compose stop nginx
   ```

2. **Preserve Evidence**:
   ```bash
   # Backup current logs
   cp -r logs/ incident-logs-$(date +%Y%m%d_%H%M%S)/
   ```

3. **Assess Impact**:
   ```bash
   # Check for unauthorized access
   make logs-app | grep "401\|403\|suspicious"
   ```

#### Investigation Phase (10-60 minutes)
1. **Review Security Logs**:
   ```bash
   # Check security events
   grep "security" logs/security.log
   # Check Sentry for security alerts
   ```

2. **Check System Integrity**:
   ```bash
   # Check for unauthorized changes
   find /app -name "*.py" -mtime -1
   # Check running processes
   ps aux | grep -v "\[.*\]"
   ```

#### Recovery Actions
1. **Patch Vulnerabilities**
2. **Reset Credentials**:
   ```bash
   # Rotate API keys
   # Update secrets in .env
   ```
3. **Enhance Monitoring**
4. **Update Security Policies**

## Performance Optimization

### Application Performance

#### CPU Optimization
```bash
# Check CPU usage patterns
make logs-app | grep "cpu_usage"

# Optimize worker count
make scale-app WORKERS=$(nproc)

# Check for CPU-intensive operations
make shell-app
python -m cProfile -s cumulative app.py
```

#### Memory Optimization
```bash
# Monitor memory usage
make stats

# Check for memory leaks
make logs-app | grep "memory_usage"

# Optimize model loading
# Configure model quantization in settings
```

#### Database Optimization
```bash
# Check Redis performance
make db-info | grep -E "used_memory|keyspace"

# Optimize Redis configuration
# Add to redis.conf:
# maxmemory 2gb
# maxmemory-policy allkeys-lru
```

### Model Performance

#### Whisper STT Optimization
```bash
# Use appropriate model size for hardware
# Configure in .env:
VOICEHELPDESK_WHISPER_MODEL=base  # or small, medium, large

# Enable GPU acceleration if available
VOICEHELPDESK_USE_GPU=true
```

#### LLM Optimization
```bash
# Optimize token usage
# Configure in .env:
VOICEHELPDESK_MAX_TOKENS=150
VOICEHELPDESK_TEMPERATURE=0.7

# Use response caching
VOICEHELPDESK_ENABLE_CACHE=true
```

### Infrastructure Scaling

#### Horizontal Scaling
```bash
# Scale based on load
make scale-app WORKERS=8
make scale-celery WORKERS=12

# Monitor resource usage
make stats
```

#### Load Balancing
```bash
# Configure Nginx upstream
# Edit nginx.conf:
upstream app {
    server app_1:8000;
    server app_2:8000;
    server app_3:8000;
}
```

## Deployment & Rollback

### Deployment Process

#### Pre-deployment Checklist
- [ ] All tests pass
- [ ] Code review completed
- [ ] Configuration reviewed
- [ ] Backup created
- [ ] Staging environment tested

#### Deployment Steps
```bash
# 1. Create backup
make backup

# 2. Pull latest code
git pull origin main

# 3. Build and deploy
make down
make build
make up

# 4. Verify deployment
make health
make ps

# 5. Run smoke tests
curl http://localhost/health
curl http://localhost/docs
```

#### Post-deployment Verification
```bash
# Check metrics
curl http://localhost:8001/metrics

# Check logs for errors
make logs-app | tail -100

# Monitor dashboards for 15 minutes
make open-grafana
```

### Rollback Process

#### Quick Rollback
```bash
# 1. Stop current services
make down

# 2. Checkout previous version
git checkout <previous-tag>

# 3. Deploy previous version
make up-build

# 4. Verify rollback
make health
```

#### Database Rollback
```bash
# If database changes were made
make restore BACKUP_DATE=<pre-deployment-backup>
```

### Zero-Downtime Deployment

#### Blue-Green Deployment
```bash
# 1. Start new version on different ports
COMPOSE_FILE=docker-compose.blue.yml make up

# 2. Health check new version
curl http://localhost:8001/health

# 3. Switch traffic (update nginx config)
# 4. Stop old version
COMPOSE_FILE=docker-compose.green.yml make down
```

## Contact Information

### Emergency Escalation
1. **Primary On-Call**: [Contact Info]
2. **Secondary On-Call**: [Contact Info]
3. **Engineering Manager**: [Contact Info]
4. **VP Engineering**: [Contact Info]

### Team Contacts
- **DevOps Team**: [Contact Info]
- **ML Engineering**: [Contact Info]
- **Product Team**: [Contact Info]
- **Security Team**: [Contact Info]

### External Vendors
- **Cloud Provider**: [Support Info]
- **OpenAI Support**: [Support Info]
- **Monitoring Vendor**: [Support Info]

---

**Document Version**: 1.0
**Last Updated**: 2024-01-01
**Next Review Date**: 2024-04-01
**Owner**: DevOps Team

> **Note**: This runbook should be regularly updated based on operational experience and system changes. All team members should be familiar with the procedures relevant to their role.