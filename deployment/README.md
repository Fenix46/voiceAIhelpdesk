# VoiceHelpDeskAI Deployment Guide

Complete production deployment infrastructure for VoiceHelpDeskAI using Docker and Docker Compose.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer/CDN                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                        Nginx Proxy                              │
│                     (SSL, Caching, Security)                    │
└─────────────┬───────────────────────────────┬───────────────────┘
              │                               │
┌─────────────▼───────────────┐    ┌─────────▼───────────────────┐
│     VoiceHelpDeskAI App     │    │      Monitoring Stack      │
│                             │    │                             │
│  ┌─────────────────────┐    │    │  ┌─────────────────────┐    │
│  │   FastAPI Server    │    │    │  │    Prometheus       │    │
│  │   (4 workers)      │    │    │  │                     │    │
│  └─────────────────────┘    │    │  └─────────────────────┘    │
│                             │    │  ┌─────────────────────┐    │
│  ┌─────────────────────┐    │    │  │      Grafana        │    │
│  │   Celery Workers    │    │    │  │                     │    │
│  │   (Background)      │    │    │  └─────────────────────┘    │
│  └─────────────────────┘    │    │  ┌─────────────────────┐    │
│                             │    │  │       Loki          │    │
│  ┌─────────────────────┐    │    │  │   (Log Storage)     │    │
│  │   AI Models         │    │    │  └─────────────────────┘    │
│  │   (Whisper, Piper)  │    │    └─────────────────────────────┘
│  └─────────────────────┘    │
└─────────────┬───────────────┘
              │
┌─────────────▼───────────────┐
│          Redis              │
│  (Cache, Sessions, Queue)   │
└─────────────────────────────┘
```

## 📋 Components

### Core Services
- **VoiceHelpDeskAI Application**: Main FastAPI application with AI models
- **Celery Workers**: Background task processing for audio and AI operations
- **Redis**: Caching, session storage, and message queue
- **Nginx**: Reverse proxy, load balancing, SSL termination

### Monitoring Stack
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Dashboards and visualization
- **Loki**: Log aggregation and querying
- **Promtail**: Log collection agent
- **Node Exporter**: System metrics
- **Redis Exporter**: Redis metrics

### Optional Services
- **Flower**: Celery task monitoring
- **Adminer**: Database administration (dev only)
- **Mailhog**: Email testing (dev only)

## 🚀 Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM
- 20GB+ disk space
- (Optional) NVIDIA GPU with Docker GPU support

### Basic Deployment

1. **Clone and navigate to deployment directory**:
   ```bash
   cd deployment/
   ```

2. **Copy and configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your specific configuration
   ```

3. **Create required directories**:
   ```bash
   mkdir -p {data,logs,models,uploads,ssl}
   chmod 755 {data,logs,models,uploads}
   ```

4. **Generate SSL certificates** (for production):
   ```bash
   # Self-signed (for testing)
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout ssl/key.pem -out ssl/cert.pem

   # Or use Let's Encrypt
   # certbot certonly --standalone -d yourdomain.com
   ```

5. **Start the stack**:
   ```bash
   # Full production stack
   docker-compose up -d

   # Or development mode
   docker-compose --profile dev up -d
   ```

6. **Verify deployment**:
   ```bash
   # Check service status
   docker-compose ps

   # Check logs
   docker-compose logs -f app

   # Test health endpoint
   curl http://localhost/health
   ```

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Application
VOICEHELPDESK_ENV=production
VOICEHELPDESK_SECRET_KEY=your-secret-key
VOICEHELPDESK_API_WORKERS=4

# Database
VOICEHELPDESK_DATABASE_URL=sqlite:///app/data/voicehelpdesk.db
VOICEHELPDESK_REDIS_URL=redis://redis:6379/0

# AI Models
VOICEHELPDESK_WHISPER_MODEL=base
VOICEHELPDESK_PIPER_MODEL=en_US-amy-medium
OPENAI_API_KEY=your-openai-key

# Monitoring
GRAFANA_PASSWORD=secure-password
FLOWER_PASSWORD=secure-password
```

### Service Scaling

Scale services based on load:

```bash
# Scale app workers
docker-compose up -d --scale app=3

# Scale celery workers
docker-compose up -d --scale celery-worker=6

# Update resource limits
# Edit docker-compose.yml and restart
```

### GPU Support

Enable GPU acceleration for AI models:

1. Install NVIDIA Docker runtime
2. Uncomment GPU configuration in `docker-compose.yml`
3. Set GPU device in environment:
   ```bash
   VOICEHELPDESK_WHISPER_DEVICE=cuda
   VOICEHELPDESK_TORCH_DEVICE=cuda
   ```

## 📊 Monitoring

### Access Dashboards

- **Grafana**: http://localhost:3000/grafana (admin/admin)
- **Prometheus**: http://localhost:9090/prometheus
- **Flower**: http://localhost:5555 (admin/admin)

### Key Metrics

- **Application Performance**: Response times, error rates, throughput
- **Audio Processing**: STT/TTS latency, queue depth, success rates
- **AI Models**: Inference time, model loading, accuracy scores
- **Infrastructure**: CPU, memory, disk, network usage
- **Business Metrics**: Conversation completion, user satisfaction

### Alerting

Prometheus alerting rules monitor:
- Application downtime
- High error rates
- Resource exhaustion
- Model performance degradation
- Queue backlogs

Configure alerting destinations in `prometheus/prometheus.yml`.

## 🔒 Security

### Default Security Features

- **Non-root containers**: All services run as non-root users
- **Network isolation**: Services on separate networks
- **Resource limits**: Memory and CPU constraints
- **SSL/TLS**: HTTPS encryption for all external traffic
- **Security headers**: OWASP recommended headers
- **Rate limiting**: Request throttling and IP-based limits

### Production Hardening

1. **Change default passwords**:
   ```bash
   # Generate secure passwords
   openssl rand -base64 32
   ```

2. **Configure firewall**:
   ```bash
   # Only expose necessary ports
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```

3. **Enable authentication**:
   ```bash
   # Add basic auth for monitoring endpoints
   htpasswd -c nginx/.htpasswd admin
   ```

4. **Regular updates**:
   ```bash
   # Update images
   docker-compose pull
   docker-compose up -d
   ```

## 📈 Performance Tuning

### Application Optimization

```yaml
# docker-compose.yml adjustments
services:
  app:
    environment:
      - VOICEHELPDESK_API_WORKERS=8  # 2x CPU cores
      - VOICEHELPDESK_API_TIMEOUT=60
    deploy:
      resources:
        limits:
          memory: 4g
          cpus: '2.0'
```

### Redis Optimization

```bash
# config/redis.conf adjustments
maxmemory 1gb
maxmemory-policy allkeys-lru
save 300 10  # Less frequent saves
```

### Nginx Optimization

```nginx
# nginx/nginx.conf adjustments
worker_processes auto;
worker_connections 8192;
keepalive_requests 10000;
```

## 🔄 Backup and Recovery

### Automated Backups

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups/$DATE"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup application data
docker run --rm -v voicehelpdesk_app-data:/data \
  -v $(pwd)/backups:/backup alpine \
  tar czf /backup/$DATE/app-data.tar.gz /data

# Backup Redis data
docker exec voicehelpdesk-redis redis-cli BGSAVE
docker cp voicehelpdesk-redis:/data/dump.rdb $BACKUP_DIR/

# Backup configuration
cp -r {.env,config/,grafana/,prometheus/} $BACKUP_DIR/

echo "Backup completed: $BACKUP_DIR"
```

### Restore Process

```bash
#!/bin/bash
# restore.sh
BACKUP_DATE=$1

# Stop services
docker-compose down

# Restore data
docker run --rm -v voicehelpdesk_app-data:/data \
  -v $(pwd)/backups:/backup alpine \
  tar xzf /backup/$BACKUP_DATE/app-data.tar.gz -C /

# Restore Redis
docker cp backups/$BACKUP_DATE/dump.rdb voicehelpdesk-redis:/data/

# Restart services
docker-compose up -d
```

## 🚨 Troubleshooting

### Common Issues

1. **Application won't start**:
   ```bash
   # Check logs
   docker-compose logs app
   
   # Verify configuration
   docker-compose config
   
   # Check resource usage
   docker stats
   ```

2. **High memory usage**:
   ```bash
   # Monitor memory
   docker stats --no-stream
   
   # Reduce model size
   VOICEHELPDESK_WHISPER_MODEL=tiny
   
   # Limit worker processes
   VOICEHELPDESK_API_WORKERS=2
   ```

3. **SSL certificate issues**:
   ```bash
   # Check certificate validity
   openssl x509 -in ssl/cert.pem -text -noout
   
   # Test SSL
   curl -k https://localhost/health
   ```

4. **Database connectivity**:
   ```bash
   # Check Redis connection
   docker exec voicehelpdesk-redis redis-cli ping
   
   # Monitor connections
   docker exec voicehelpdesk-redis redis-cli info clients
   ```

### Performance Issues

1. **Slow response times**:
   - Check CPU/memory usage
   - Monitor Grafana dashboards
   - Increase worker count
   - Enable caching

2. **Audio processing delays**:
   - Check queue depth
   - Scale celery workers
   - Optimize model parameters
   - Use GPU acceleration

### Log Analysis

```bash
# Application logs
docker-compose logs -f app

# Error patterns
docker-compose logs app | grep ERROR

# Performance metrics
docker-compose logs app | grep "response_time"

# Celery task status
docker-compose logs celery-worker | grep "Task"
```

## 🔄 Updates and Maintenance

### Regular Maintenance

```bash
#!/bin/bash
# maintenance.sh

# Update images
docker-compose pull

# Clean up unused resources
docker system prune -f

# Restart services (rolling update)
docker-compose up -d --force-recreate --no-deps app

# Backup after update
./backup.sh
```

### Zero-Downtime Updates

```bash
# Scale up new version
docker-compose up -d --scale app=6

# Health check new instances
curl http://localhost/health

# Scale down old instances
docker-compose up -d --scale app=3

# Remove old containers
docker-compose up -d --remove-orphans
```

## 📞 Support

### Health Checks

- **Application**: `GET /health`
- **Metrics**: `GET /metrics` 
- **API Docs**: `GET /docs`

### Monitoring Endpoints

- **Prometheus**: `:9090/targets`
- **Grafana**: `:3000/grafana/api/health`
- **Redis**: `:6379` (redis-cli ping)

### Log Locations

- **Application**: `/var/log/app/`
- **Nginx**: `/var/log/nginx/`
- **System**: `/var/log/`

For additional support, check the project documentation or open an issue.