.PHONY: help install install-dev install-prod clean test test-cov lint format type-check security pre-commit run dev docker-build docker-run docker-down migrate create-migration backup restore logs

# Default target
help:
	@echo "VoiceHelpDeskAI Development Commands"
	@echo "======================================"
	@echo
	@echo "Setup Commands:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo "  make install-prod     Install production dependencies only"
	@echo "  make setup-dev        Complete development setup"
	@echo
	@echo "Development Commands:"
	@echo "  make run              Run the application"
	@echo "  make dev              Run in development mode with reload"
	@echo "  make test             Run tests"
	@echo "  make test-cov         Run tests with coverage"
	@echo "  make lint             Run all linters"
	@echo "  make format           Format code with black and isort"
	@echo "  make type-check       Run type checking with mypy"
	@echo "  make security         Run security checks"
	@echo
	@echo "Docker Commands:"
	@echo "  make docker-build     Build Docker images"
	@echo "  make docker-run       Run with Docker Compose"
	@echo "  make docker-down      Stop Docker containers"
	@echo "  make docker-logs      View Docker logs"
	@echo
	@echo "Database Commands:"
	@echo "  make migrate          Run database migrations"
	@echo "  make create-migration Create new migration"
	@echo "  make reset-db         Reset database"
	@echo
	@echo "Utility Commands:"
	@echo "  make clean            Clean up generated files"
	@echo "  make pre-commit       Run pre-commit hooks"
	@echo "  make logs             View application logs"

# Installation commands
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

install-prod:
	pip install -e ".[prod]"

setup-dev: install-dev
	mkdir -p logs uploads audio_files data
	cp .env.example .env
	@echo "Development environment setup complete!"
	@echo "Don't forget to update .env with your configuration."

# Development commands
run:
	uvicorn voicehelpdeskai.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn voicehelpdeskai.main:app --host 0.0.0.0 --port 8000 --reload

# Testing commands
test:
	pytest tests/

test-cov:
	pytest --cov=voicehelpdeskai --cov-report=html --cov-report=term-missing tests/

test-unit:
	pytest tests/unit/

test-integration:
	pytest tests/integration/

# Code quality commands
lint: lint-flake8 lint-mypy lint-bandit

lint-flake8:
	flake8 src/ tests/

lint-mypy:
	mypy src/voicehelpdeskai

lint-bandit:
	bandit -r src/voicehelpdeskai

format:
	black src/ tests/
	isort src/ tests/

format-check:
	black --check src/ tests/
	isort --check-only src/ tests/

type-check:
	mypy src/voicehelpdeskai

security:
	bandit -r src/voicehelpdeskai
	safety check

# Pre-commit
pre-commit:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate

# Docker commands
docker-build:
	docker-compose build

docker-run:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	docker-compose down -v --remove-orphans
	docker system prune -f

# Database commands
migrate:
	alembic upgrade head

create-migration:
	@read -p "Enter migration message: " message; \
	alembic revision --autogenerate -m "$$message"

reset-db:
	rm -f app.db
	alembic upgrade head

# Celery commands
celery-worker:
	celery -A voicehelpdeskai.core.celery worker --loglevel=info

celery-beat:
	celery -A voicehelpdeskai.core.celery beat --loglevel=info

celery-flower:
	celery -A voicehelpdeskai.core.celery flower

# Monitoring and logs
logs:
	tail -f logs/app.log

logs-error:
	grep ERROR logs/app.log | tail -20

monitor:
	@echo "Application Health Check:"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "Service not running"

# Cleanup commands
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

clean-all: clean
	rm -rf venv/
	rm -rf node_modules/
	rm -f .env

# Requirements generation
requirements:
	pip-compile pyproject.toml

requirements-dev:
	pip-compile --extra dev pyproject.toml

requirements-prod:
	pip-compile --extra prod pyproject.toml

# Backup and restore
backup:
	@echo "Creating backup..."
	mkdir -p backups
	cp app.db backups/app_$(shell date +%Y%m%d_%H%M%S).db
	tar -czf backups/audio_files_$(shell date +%Y%m%d_%H%M%S).tar.gz audio_files/

restore:
	@echo "Available backups:"
	@ls -la backups/
	@read -p "Enter backup file to restore: " backup; \
	cp backups/$$backup app.db

# Production deployment helpers
deploy-check:
	@echo "Running deployment checks..."
	python -m voicehelpdeskai.core.health_check
	make test
	make security
	@echo "✅ Deployment checks passed!"

# Environment management
env-example:
	@echo "Updating .env.example with current environment variables..."
	@grep -v '^#' .env | sort > .env.example.tmp
	@mv .env.example.tmp .env.example