# VoiceHelpDeskAI Deployment Guide

## Table of Contents
1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Environment Setup](#environment-setup)
4. [Docker Deployment](#docker-deployment)
5. [Production Deployment](#production-deployment)
6. [Kubernetes Deployment](#kubernetes-deployment)
7. [Configuration Management](#configuration-management)
8. [Monitoring Setup](#monitoring-setup)
9. [Security Configuration](#security-configuration)
10. [Troubleshooting](#troubleshooting)

## Overview

This guide covers deploying VoiceHelpDeskAI across different environments, from local development to production Kubernetes clusters. The system is designed to be cloud-native and supports various deployment patterns.

### Deployment Options
- **Local Development**: Docker Compose
- **Single Server**: Docker Compose with SSL
- **Cloud Deployment**: Docker with cloud services
- **Kubernetes**: Full orchestration with Helm charts
- **Hybrid**: Mix of managed and self-hosted services

## System Requirements

### Minimum Requirements (Development)
- **CPU**: 4 cores, 2.4 GHz
- **RAM**: 8 GB
- **Storage**: 50 GB SSD
- **Network**: Broadband internet connection
- **OS**: Linux, macOS, or Windows with WSL2

### Recommended Requirements (Production)
- **CPU**: 8+ cores, 3.0+ GHz
- **RAM**: 32+ GB
- **Storage**: 200+ GB SSD (with backup storage)
- **Network**: Dedicated connection, low latency
- **GPU**: Optional NVIDIA GPU for local AI models

### Software Dependencies
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.11+ (for development)
- **Git**: Latest version
- **Make**: For automation scripts

## Environment Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-org/VoiceHelpDeskAI.git
cd VoiceHelpDeskAI
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 3. Essential Environment Variables
```bash
# Application Settings
VOICEHELPDESK_ENV=production
VOICEHELPDESK_DEBUG=false
VOICEHELPDESK_LOG_LEVEL=INFO
VOICEHELPDESK_VERSION=1.0.0

# Database Configuration
VOICEHELPDESK_DATABASE_URL=postgresql://user:password@localhost:5432/voicehelpdesk
VOICEHELPDESK_REDIS_URL=redis://localhost:6379/0

# AI Service Configuration
OPENAI_API_KEY=your-openai-api-key
VOICEHELPDESK_WHISPER_MODEL=base
VOICEHELPDESK_PIPER_MODEL=en_US-amy-medium

# Security Settings
VOICEHELPDESK_SECRET_KEY=your-secret-key-here
VOICEHELPDESK_ALLOWED_HOSTS=yourdomain.com,localhost
VOICEHELPDESK_CORS_ORIGINS=https://yourdomain.com

# External Services
VOICEHELPDESK_SMTP_SERVER=smtp.gmail.com
VOICEHELPDESK_SMTP_PORT=587
VOICEHELPDESK_SMTP_USERNAME=your-email@gmail.com
VOICEHELPDESK_SMTP_PASSWORD=your-app-password

# Monitoring
SENTRY_DSN=your-sentry-dsn
VOICEHELPDESK_PROMETHEUS_ENABLED=true
```

## Docker Deployment

### Development Environment

#### Quick Start
```bash
# Initialize development environment
make setup-dev

# Start all services
make dev

# Check service status
make ps

# View logs
make logs
```

#### Manual Setup
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Run database migrations
docker-compose exec app alembic upgrade head

# Create initial data
docker-compose exec app python scripts/seed_data.py
```

### Production Docker Setup

#### 1. Production Docker Compose
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - VOICEHELPDESK_ENV=production
    env_file:
      - .env.prod
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile.prod
    command: celery -A voicehelpdeskai.core.celery worker --loglevel=info
    environment:
      - VOICEHELPDESK_ENV=production
    env_file:
      - .env.prod
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    deploy:
      replicas: 4

  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile.prod
    command: celery -A voicehelpdeskai.core.celery beat --loglevel=info
    environment:
      - VOICEHELPDESK_ENV=production
    env_file:
      - .env.prod
    depends_on:
      - redis
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - app
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: voicehelpdesk
      POSTGRES_USER: voicehelpdesk
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U voicehelpdesk"]
      interval: 30s
      timeout: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

#### 2. Production Dockerfile
```dockerfile
# Dockerfile.prod
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/base.txt requirements/prod.txt ./
RUN pip install --no-cache-dir -r prod.txt

FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create app user
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to app user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "voicehelpdeskai.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 3. Deploy to Production
```bash
# Set production environment
export COMPOSE_FILE=docker-compose.prod.yml

# Deploy
make prod-deploy

# Scale services
docker-compose up -d --scale celery-worker=6

# Monitor deployment
make health
make logs
```

## Production Deployment

### Cloud Provider Setup

#### AWS Deployment
```bash
# 1. Create infrastructure
terraform -chdir=terraform/aws init
terraform -chdir=terraform/aws plan
terraform -chdir=terraform/aws apply

# 2. Configure DNS
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456789 \
  --change-batch file://dns-change.json

# 3. Deploy application
docker-compose -f docker-compose.aws.yml up -d

# 4. Setup load balancer health checks
aws elbv2 create-target-group \
  --name voicehelpdesk-targets \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-12345678 \
  --health-check-path /health
```

#### Google Cloud Platform
```bash
# 1. Setup GKE cluster
gcloud container clusters create voicehelpdesk-cluster \
  --num-nodes=3 \
  --machine-type=n1-standard-4 \
  --zone=us-central1-a

# 2. Deploy with Helm
helm repo add voicehelpdesk ./helm/voicehelpdesk
helm install voicehelpdesk voicehelpdesk/voicehelpdesk \
  --set image.tag=latest \
  --set ingress.enabled=true \
  --set ingress.hostname=voicehelpdesk.example.com

# 3. Setup Cloud SQL
gcloud sql instances create voicehelpdesk-db \
  --database-version=POSTGRES_13 \
  --tier=db-n1-standard-2 \
  --region=us-central1
```

#### Azure Deployment
```bash
# 1. Create resource group
az group create --name voicehelpdesk-rg --location eastus

# 2. Create AKS cluster
az aks create \
  --resource-group voicehelpdesk-rg \
  --name voicehelpdesk-aks \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-addons monitoring

# 3. Deploy application
kubectl apply -f k8s/azure/
```

### SSL/TLS Configuration

#### Let's Encrypt with Nginx
```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificates
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

#### Custom SSL Certificate
```nginx
# nginx/ssl.conf
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    
    location / {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Kubernetes Deployment

### Helm Chart Structure
```
helm/voicehelpdesk/
├── Chart.yaml
├── values.yaml
├── values-prod.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── hpa.yaml
│   └── rbac.yaml
└── charts/
    ├── redis/
    └── postgresql/
```

#### Application Deployment
```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "voicehelpdesk.fullname" . }}
  labels:
    {{- include "voicehelpdesk.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "voicehelpdesk.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "voicehelpdesk.selectorLabels" . | nindent 8 }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: 8000
          protocol: TCP
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          {{- toYaml .Values.resources | nindent 12 }}
        env:
        - name: VOICEHELPDESK_ENV
          value: "production"
        - name: VOICEHELPDESK_DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: {{ include "voicehelpdesk.fullname" . }}-secret
              key: database-url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: {{ include "voicehelpdesk.fullname" . }}-secret
              key: openai-api-key
```

#### Celery Workers
```yaml
# templates/celery-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "voicehelpdesk.fullname" . }}-celery
spec:
  replicas: {{ .Values.celery.replicaCount }}
  selector:
    matchLabels:
      app: {{ include "voicehelpdesk.name" . }}-celery
  template:
    metadata:
      labels:
        app: {{ include "voicehelpdesk.name" . }}-celery
    spec:
      containers:
      - name: celery-worker
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        command: ["celery"]
        args: ["-A", "voicehelpdeskai.core.celery", "worker", "--loglevel=info"]
        resources:
          {{- toYaml .Values.celery.resources | nindent 12 }}
        env:
        - name: VOICEHELPDESK_ENV
          value: "production"
        # ... (same env vars as main app)
```

#### Horizontal Pod Autoscaler
```yaml
# templates/hpa.yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "voicehelpdesk.fullname" . }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "voicehelpdesk.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
  {{- if .Values.autoscaling.targetCPUUtilizationPercentage }}
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
  {{- end }}
  {{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
  {{- end }}
{{- end }}
```

#### Production Values
```yaml
# values-prod.yaml
replicaCount: 3

image:
  repository: voicehelpdesk/app
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8000

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  hosts:
    - host: voicehelpdesk.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: voicehelpdesk-tls
      hosts:
        - voicehelpdesk.example.com

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

celery:
  replicaCount: 6
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 500m
      memory: 1Gi

postgresql:
  enabled: true
  auth:
    postgresPassword: "secure-password"
    database: "voicehelpdesk"
  primary:
    persistence:
      enabled: true
      size: 100Gi

redis:
  enabled: true
  auth:
    enabled: false
  master:
    persistence:
      enabled: true
      size: 20Gi
```

#### Deploy to Kubernetes
```bash
# Add Helm repository
helm repo add bitnami https://charts.bitnami.com/bitnami

# Install dependencies
helm dependency update helm/voicehelpdesk

# Deploy to production
helm install voicehelpdesk helm/voicehelpdesk \
  -f helm/voicehelpdesk/values-prod.yaml \
  --namespace voicehelpdesk \
  --create-namespace

# Upgrade deployment
helm upgrade voicehelpdesk helm/voicehelpdesk \
  -f helm/voicehelpdesk/values-prod.yaml \
  --namespace voicehelpdesk

# Monitor deployment
kubectl get pods -n voicehelpdesk
kubectl logs -f deployment/voicehelpdesk -n voicehelpdesk
```

## Configuration Management

### Environment-Specific Configs

#### Development (.env.dev)
```bash
VOICEHELPDESK_ENV=development
VOICEHELPDESK_DEBUG=true
VOICEHELPDESK_LOG_LEVEL=DEBUG
VOICEHELPDESK_DATABASE_URL=sqlite:///./data/dev.db
VOICEHELPDESK_REDIS_URL=redis://localhost:6379/0
VOICEHELPDESK_WHISPER_MODEL=tiny
VOICEHELPDESK_ENABLE_PROFILING=true
```

#### Staging (.env.staging)
```bash
VOICEHELPDESK_ENV=staging
VOICEHELPDESK_DEBUG=false
VOICEHELPDESK_LOG_LEVEL=INFO
VOICEHELPDESK_DATABASE_URL=postgresql://user:pass@staging-db:5432/voicehelpdesk
VOICEHELPDESK_REDIS_URL=redis://staging-redis:6379/0
VOICEHELPDESK_WHISPER_MODEL=base
SENTRY_DSN=https://staging-dsn@sentry.io/project
```

#### Production (.env.prod)
```bash
VOICEHELPDESK_ENV=production
VOICEHELPDESK_DEBUG=false
VOICEHELPDESK_LOG_LEVEL=WARNING
VOICEHELPDESK_DATABASE_URL=postgresql://user:pass@prod-db:5432/voicehelpdesk
VOICEHELPDESK_REDIS_URL=redis://prod-redis:6379/0
VOICEHELPDESK_WHISPER_MODEL=base
SENTRY_DSN=https://prod-dsn@sentry.io/project
VOICEHELPDESK_CORS_ORIGINS=https://app.yourdomain.com
```

### Secret Management

#### HashiCorp Vault Integration
```python
# config/vault.py
import hvac

class VaultConfig:
    def __init__(self, url: str, token: str):
        self.client = hvac.Client(url=url, token=token)
    
    def get_secret(self, path: str, key: str) -> str:
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        return response['data']['data'][key]

# Usage
vault = VaultConfig(
    url=os.getenv('VAULT_URL'),
    token=os.getenv('VAULT_TOKEN')
)

OPENAI_API_KEY = vault.get_secret('voicehelpdesk/prod', 'openai_api_key')
```

#### Kubernetes Secrets
```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: voicehelpdesk-secrets
type: Opaque
data:
  database-url: <base64-encoded-url>
  openai-api-key: <base64-encoded-key>
  secret-key: <base64-encoded-secret>
```

## Monitoring Setup

### Prometheus Configuration
```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'voicehelpdesk'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx-exporter:9113']
```

### Grafana Provisioning
```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

### Alert Rules
```yaml
# prometheus/rules/voicehelpdesk.yml
groups:
- name: voicehelpdesk
  rules:
  - alert: HighResponseTime
    expr: histogram_quantile(0.95, voicehelpdesk_http_request_duration_seconds_bucket) > 2
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High response time detected"
      
  - alert: HighErrorRate
    expr: rate(voicehelpdesk_http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
```

## Security Configuration

### Firewall Rules
```bash
# UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow from 10.0.0.0/8 to any port 8000  # Internal API access
sudo ufw --force enable
```

### Docker Security
```yaml
# docker-compose.override.yml (security hardening)
version: '3.8'

services:
  app:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
      - /var/tmp
    user: "1000:1000"
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

### Network Policies (Kubernetes)
```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: voicehelpdesk-netpol
spec:
  podSelector:
    matchLabels:
      app: voicehelpdesk
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
  - to:
    - podSelector:
        matchLabels:
          app: postgresql
    ports:
    - protocol: TCP
      port: 5432
```

## Troubleshooting

### Common Issues

#### 1. Application Won't Start
```bash
# Check logs
docker-compose logs app

# Common fixes
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check environment variables
docker-compose exec app env | grep VOICEHELPDESK
```

#### 2. Database Connection Issues
```bash
# Test database connectivity
docker-compose exec app python -c "
from voicehelpdeskai.config import config_manager
from sqlalchemy import create_engine
engine = create_engine(config_manager.get('VOICEHELPDESK_DATABASE_URL'))
print('Database connection successful')
"

# Check database logs
docker-compose logs postgres
```

#### 3. Redis Connection Issues
```bash
# Test Redis connectivity
docker-compose exec app python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
print(r.ping())
"

# Check Redis logs
docker-compose logs redis
```

#### 4. Audio Processing Issues
```bash
# Check audio dependencies
docker-compose exec app python -c "
import soundfile
import librosa
import whisper
print('Audio dependencies loaded successfully')
"

# Check model files
docker-compose exec app ls -la /app/models/
```

### Performance Troubleshooting

#### Resource Usage
```bash
# Monitor resource usage
docker stats

# Check disk usage
docker system df
docker volume ls

# Clean up unused resources
docker system prune -a
```

#### Database Performance
```sql
-- Check slow queries (PostgreSQL)
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes 
ORDER BY idx_tup_read DESC;
```

### Debugging Tools

#### Application Debug Mode
```bash
# Enable debug mode
export VOICEHELPDESK_DEBUG=true
export VOICEHELPDESK_LOG_LEVEL=DEBUG

# Restart with debug logs
docker-compose restart app
docker-compose logs -f app
```

#### Health Check Script
```bash
#!/bin/bash
# health_check.sh

echo "=== VoiceHelpDeskAI Health Check ==="

# Check services
docker-compose ps

# Check application health
curl -f http://localhost/health || echo "❌ Application health check failed"

# Check Redis
docker-compose exec redis redis-cli ping || echo "❌ Redis check failed"

# Check database
docker-compose exec postgres pg_isready || echo "❌ Database check failed"

# Check disk space
df -h

# Check memory usage
free -m

echo "=== Health Check Complete ==="
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Database migrations tested
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Security hardening applied
- [ ] Load testing completed

### During Deployment
- [ ] Blue-green deployment strategy
- [ ] Health checks passing
- [ ] Gradual traffic migration
- [ ] Rollback plan ready
- [ ] Team notification sent

### Post-Deployment
- [ ] End-to-end testing
- [ ] Performance monitoring
- [ ] Error rate monitoring
- [ ] User acceptance testing
- [ ] Documentation updated

For more information, see:
- [Configuration Reference](configuration.md)
- [Troubleshooting Guide](troubleshooting.md)
- [Security Guide](security.md)
- [Performance Tuning](performance.md)