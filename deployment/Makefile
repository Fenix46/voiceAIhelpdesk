# VoiceHelpDeskAI Deployment Makefile
# Simplified commands for Docker deployment and management

# Default environment
ENV ?= production
COMPOSE_FILE ?= docker-compose.yml
PROJECT_NAME ?= voicehelpdesk

# Docker Compose command with project name
DOCKER_COMPOSE = docker-compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE)

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[0;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

.PHONY: help build up down restart logs ps clean setup-dirs setup-ssl config health backup restore update

# Default target
help: ## Show this help message
	@echo "$(BLUE)VoiceHelpDeskAI Deployment Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Basic Operations:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# =============================================================================
# Setup and Configuration
# =============================================================================

setup: setup-dirs setup-env ## Initial setup (directories and environment)
	@echo "$(GREEN)✓ Setup complete$(NC)"

setup-dirs: ## Create required directories
	@echo "$(BLUE)Creating directories...$(NC)"
	@mkdir -p data logs models uploads ssl config
	@chmod 755 data logs models uploads
	@echo "$(GREEN)✓ Directories created$(NC)"

setup-env: ## Copy environment template
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)⚠ Please edit .env with your configuration$(NC)"; \
	else \
		echo "$(GREEN)✓ .env already exists$(NC)"; \
	fi

setup-ssl: ## Generate self-signed SSL certificates
	@echo "$(BLUE)Generating SSL certificates...$(NC)"
	@mkdir -p ssl
	@if [ ! -f ssl/cert.pem ] || [ ! -f ssl/key.pem ]; then \
		openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
			-keyout ssl/key.pem -out ssl/cert.pem \
			-subj "/C=US/ST=State/L=City/O=VoiceHelpDesk/CN=localhost"; \
		echo "$(GREEN)✓ SSL certificates generated$(NC)"; \
	else \
		echo "$(GREEN)✓ SSL certificates already exist$(NC)"; \
	fi

config: ## Validate Docker Compose configuration
	@$(DOCKER_COMPOSE) config

# =============================================================================
# Build and Run
# =============================================================================

build: ## Build Docker images
	@echo "$(BLUE)Building images...$(NC)"
	@$(DOCKER_COMPOSE) build --parallel
	@echo "$(GREEN)✓ Build complete$(NC)"

build-no-cache: ## Build Docker images without cache
	@echo "$(BLUE)Building images without cache...$(NC)"
	@$(DOCKER_COMPOSE) build --no-cache --parallel
	@echo "$(GREEN)✓ Build complete$(NC)"

up: ## Start all services
	@echo "$(BLUE)Starting services...$(NC)"
	@$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@make ps

up-build: ## Build and start all services
	@echo "$(BLUE)Building and starting services...$(NC)"
	@$(DOCKER_COMPOSE) up -d --build
	@echo "$(GREEN)✓ Services started$(NC)"
	@make ps

up-dev: ## Start services in development mode
	@echo "$(BLUE)Starting development services...$(NC)"
	@$(DOCKER_COMPOSE) --profile dev up -d
	@echo "$(GREEN)✓ Development services started$(NC)"
	@make ps

down: ## Stop and remove all services
	@echo "$(BLUE)Stopping services...$(NC)"
	@$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✓ Services stopped$(NC)"

down-volumes: ## Stop services and remove volumes
	@echo "$(RED)Stopping services and removing volumes...$(NC)"
	@$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)✓ Services stopped and volumes removed$(NC)"

restart: ## Restart all services
	@echo "$(BLUE)Restarting services...$(NC)"
	@$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

restart-app: ## Restart only the application
	@echo "$(BLUE)Restarting application...$(NC)"
	@$(DOCKER_COMPOSE) restart app
	@echo "$(GREEN)✓ Application restarted$(NC)"

# =============================================================================
# Monitoring and Logs
# =============================================================================

ps: ## Show service status
	@echo "$(BLUE)Service Status:$(NC)"
	@$(DOCKER_COMPOSE) ps

logs: ## Show logs for all services
	@$(DOCKER_COMPOSE) logs -f

logs-app: ## Show application logs
	@$(DOCKER_COMPOSE) logs -f app

logs-celery: ## Show Celery worker logs
	@$(DOCKER_COMPOSE) logs -f celery-worker

logs-nginx: ## Show Nginx logs
	@$(DOCKER_COMPOSE) logs -f nginx

logs-redis: ## Show Redis logs
	@$(DOCKER_COMPOSE) logs -f redis

health: ## Check service health
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo "Application Health:"
	@curl -s http://localhost/health | jq . || echo "$(RED)✗ Application unhealthy$(NC)"
	@echo "\nRedis Health:"
	@docker exec $(PROJECT_NAME)-redis redis-cli ping || echo "$(RED)✗ Redis unhealthy$(NC)"
	@echo "\nPrometheus Health:"
	@curl -s http://localhost:9090/-/healthy || echo "$(RED)✗ Prometheus unhealthy$(NC)"
	@echo "\nGrafana Health:"
	@curl -s http://localhost:3000/grafana/api/health | jq . || echo "$(RED)✗ Grafana unhealthy$(NC)"

stats: ## Show resource usage
	@echo "$(BLUE)Resource Usage:$(NC)"
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# =============================================================================
# Scaling
# =============================================================================

scale-app: ## Scale application workers (make scale-app WORKERS=4)
	@$(eval WORKERS ?= 2)
	@echo "$(BLUE)Scaling application to $(WORKERS) workers...$(NC)"
	@$(DOCKER_COMPOSE) up -d --scale app=$(WORKERS)
	@echo "$(GREEN)✓ Application scaled to $(WORKERS) workers$(NC)"

scale-celery: ## Scale Celery workers (make scale-celery WORKERS=4)
	@$(eval WORKERS ?= 2)
	@echo "$(BLUE)Scaling Celery to $(WORKERS) workers...$(NC)"
	@$(DOCKER_COMPOSE) up -d --scale celery-worker=$(WORKERS)
	@echo "$(GREEN)✓ Celery scaled to $(WORKERS) workers$(NC)"

# =============================================================================
# Maintenance
# =============================================================================

clean: ## Clean up Docker resources
	@echo "$(BLUE)Cleaning up Docker resources...$(NC)"
	@docker system prune -f
	@docker volume prune -f
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: ## Clean up all Docker resources including images
	@echo "$(RED)Cleaning up all Docker resources...$(NC)"
	@docker system prune -af
	@docker volume prune -f
	@echo "$(GREEN)✓ Complete cleanup done$(NC)"

update: ## Update images and restart services
	@echo "$(BLUE)Updating services...$(NC)"
	@$(DOCKER_COMPOSE) pull
	@$(DOCKER_COMPOSE) up -d --force-recreate
	@echo "$(GREEN)✓ Services updated$(NC)"

# =============================================================================
# Backup and Restore
# =============================================================================

backup: ## Create backup of application data
	@$(eval BACKUP_DATE := $(shell date +%Y%m%d_%H%M%S))
	@echo "$(BLUE)Creating backup $(BACKUP_DATE)...$(NC)"
	@mkdir -p backups/$(BACKUP_DATE)
	
	# Backup application data
	@docker run --rm -v $(PROJECT_NAME)_app-data:/data \
		-v $(PWD)/backups:/backup alpine \
		tar czf /backup/$(BACKUP_DATE)/app-data.tar.gz /data
	
	# Backup Redis data
	@docker exec $(PROJECT_NAME)-redis redis-cli BGSAVE
	@sleep 2
	@docker cp $(PROJECT_NAME)-redis:/data/dump.rdb backups/$(BACKUP_DATE)/
	
	# Backup configuration
	@cp -r .env config/ grafana/ prometheus/ backups/$(BACKUP_DATE)/
	
	@echo "$(GREEN)✓ Backup created: backups/$(BACKUP_DATE)$(NC)"

restore: ## Restore from backup (make restore BACKUP_DATE=20231201_120000)
	@$(eval BACKUP_DATE ?= latest)
	@if [ "$(BACKUP_DATE)" = "latest" ]; then \
		BACKUP_DATE=$$(ls -1 backups/ | tail -1); \
	fi
	@echo "$(BLUE)Restoring from backup $(BACKUP_DATE)...$(NC)"
	@$(DOCKER_COMPOSE) down
	
	# Restore application data
	@docker run --rm -v $(PROJECT_NAME)_app-data:/data \
		-v $(PWD)/backups:/backup alpine \
		tar xzf /backup/$(BACKUP_DATE)/app-data.tar.gz -C /
	
	# Restore Redis data
	@docker cp backups/$(BACKUP_DATE)/dump.rdb $(PROJECT_NAME)-redis:/data/
	
	@$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✓ Restore complete$(NC)"

# =============================================================================
# Database Operations
# =============================================================================

db-shell: ## Access Redis shell
	@docker exec -it $(PROJECT_NAME)-redis redis-cli

db-backup: ## Backup Redis database
	@echo "$(BLUE)Backing up Redis database...$(NC)"
	@docker exec $(PROJECT_NAME)-redis redis-cli BGSAVE
	@echo "$(GREEN)✓ Redis backup initiated$(NC)"

db-info: ## Show Redis information
	@docker exec $(PROJECT_NAME)-redis redis-cli info

# =============================================================================
# Development Helpers
# =============================================================================

shell-app: ## Access application shell
	@docker exec -it $(PROJECT_NAME)-app bash

shell-celery: ## Access Celery worker shell
	@docker exec -it $(PROJECT_NAME)-celery-worker bash

shell-nginx: ## Access Nginx shell
	@docker exec -it $(PROJECT_NAME)-nginx sh

test: ## Run application tests
	@echo "$(BLUE)Running tests...$(NC)"
	@docker exec $(PROJECT_NAME)-app python -m pytest
	@echo "$(GREEN)✓ Tests complete$(NC)"

migrate: ## Run database migrations
	@echo "$(BLUE)Running migrations...$(NC)"
	@docker exec $(PROJECT_NAME)-app alembic upgrade head
	@echo "$(GREEN)✓ Migrations complete$(NC)"

# =============================================================================
# Monitoring
# =============================================================================

open-grafana: ## Open Grafana in browser
	@echo "$(BLUE)Opening Grafana...$(NC)"
	@xdg-open http://localhost:3000/grafana || open http://localhost:3000/grafana || echo "Please open http://localhost:3000/grafana"

open-prometheus: ## Open Prometheus in browser
	@echo "$(BLUE)Opening Prometheus...$(NC)"
	@xdg-open http://localhost:9090 || open http://localhost:9090 || echo "Please open http://localhost:9090"

open-flower: ## Open Flower in browser
	@echo "$(BLUE)Opening Flower...$(NC)"
	@xdg-open http://localhost:5555 || open http://localhost:5555 || echo "Please open http://localhost:5555"

metrics: ## Show current metrics
	@echo "$(BLUE)Current Metrics:$(NC)"
	@curl -s http://localhost:8001/metrics | grep -E "^(voicehelpdesk_|process_|python_)" | head -20

# =============================================================================
# Production Helpers
# =============================================================================

prod-setup: setup setup-ssl ## Full production setup
	@echo "$(GREEN)✓ Production setup complete$(NC)"
	@echo "$(YELLOW)⚠ Please:"
	@echo "  1. Edit .env with production values"
	@echo "  2. Configure SSL certificates"
	@echo "  3. Set up monitoring alerts"
	@echo "  4. Configure backups$(NC)"

prod-deploy: prod-setup build up ## Deploy to production
	@echo "$(GREEN)✓ Production deployment complete$(NC)"
	@make health

# =============================================================================
# Quick Commands
# =============================================================================

start: up ## Alias for 'up'
stop: down ## Alias for 'down'
rebuild: down build up ## Rebuild and restart everything