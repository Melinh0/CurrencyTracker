# ============================================
# CurrencyTracker - Makefile
# ============================================

.PHONY: help install dev test lint format typecheck clean build up down logs shell db-migrate db-seed train predict

# Default target
help:
	@echo "CurrencyTracker - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  install      - Install dependencies"
	@echo "  dev          - Start development environment"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linters (ruff)"
	@echo "  format       - Format code (black)"
	@echo "  typecheck    - Type check (mypy)"
	@echo ""
	@echo "Docker:"
	@echo "  build        - Build Docker images"
	@echo "  up           - Start all services"
	@echo "  down         - Stop all services"
	@echo "  logs         - View logs"
	@echo "  shell        - Open shell in API container"
	@echo ""
	@echo "Database:"
	@echo "  db-migrate   - Run database migrations"
	@echo "  db-seed      - Seed initial data"
	@echo ""
	@echo "ML:"
	@echo "  train        - Train models for all currencies"
	@echo "  predict      - Generate predictions"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean        - Clean build artifacts"

# ============================================
# Development
# ============================================

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo "Development environment started!"
	@echo "API: http://localhost:8000"
	@echo "Dashboard: http://localhost:8501"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@echo "MLflow: http://localhost:5000"

test:
	pytest -v --cov=currency_tracker --cov-report=term-missing

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

lint:
	ruff check currency_tracker tests

format:
	black currency_tracker tests
	ruff check --fix currency_tracker tests

typecheck:
	mypy currency_tracker

clean:
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# ============================================
# Docker
# ============================================

build:
	docker-compose build --parallel

up:
	docker-compose up -d
	@echo "Services started!"
	@echo "API: http://localhost:8000"
	@echo "Dashboard: http://localhost:8501"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@echo "MLflow: http://localhost:5000"

down:
	docker-compose down

down-v:
	docker-compose down -v

logs:
	docker-compose logs -f --tail=100

logs-api:
	docker-compose logs -f api

logs-collector:
	docker-compose logs -f collector

logs-ml:
	docker-compose logs -f ml-trainer

logs-alerts:
	docker-compose logs -f alerts

shell:
	docker-compose exec api bash

shell-db:
	docker-compose exec postgres psql -U currency_user -d currency_tracker

# ============================================
# Database
# ============================================

db-migrate:
	docker-compose exec api alembic upgrade head

db-migrate-create:
	@read -p "Migration message: " msg; \
	docker-compose exec api alembic revision --autogenerate -m "$$msg"

db-downgrade:
	docker-compose exec api alembic downgrade -1

db-seed:
	docker-compose exec api python -m currency_tracker.scripts.seed_db

db-reset:
	docker-compose down -v postgres
	docker-compose up -d postgres
	sleep 10
	make db-migrate
	make db-seed

# ============================================
# ML Operations
# ============================================

train:
	docker-compose exec ml-trainer python -m currency_tracker.ml.training.scheduler --once

train-currency:
	@read -p "Currency (e.g., USD): " curr; \
	docker-compose exec ml-trainer python -c "import asyncio; from currency_tracker.ml.training.pipeline import train_currency_model; asyncio.run(train_currency_model('$$curr'))"

predict:
	docker-compose exec api python -m currency_tracker.ml.prediction.service --all

predict-currency:
	@read -p "Base currency (default BRL): " base; \
	read -p "Quote currency: " quote; \
	read -p "Horizon days (default 7): " horizon; \
	docker-compose exec api python -c "import asyncio; from currency_tracker.ml.prediction.service import prediction_service; asyncio.run(prediction_service.predict('$$base', '$$quote', int('$$horizon') or 7))"

# ============================================
# Collector Operations
# ============================================

collect-once:
	docker-compose exec collector python -m currency_tracker.collector.scheduler --once

collect-continuous:
	docker-compose exec collector python -m currency_tracker.collector.scheduler

# ============================================
# Monitoring
# ============================================

prometheus-reload:
	curl -X POST http://localhost:9090/-/reload

grafana-import:
	@echo "Import dashboards from monitoring/grafana/dashboards/"

# ============================================
# Utilities
# ============================================

check-config:
	docker-compose config

ps:
	docker-compose ps

top:
	docker-compose top

restart:
	docker-compose restart

update:
	git pull
	docker-compose pull
	docker-compose up -d --build