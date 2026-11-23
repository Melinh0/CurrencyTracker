# ============================================
# CurrencyTracker - Multi-stage Dockerfile
# ============================================

# --------------------------------------------
# Base Stage - Common dependencies
# --------------------------------------------
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY currency_tracker ./currency_tracker
COPY config ./config
COPY scripts ./scripts

# Change ownership
RUN chown -R appuser:appuser /app

# --------------------------------------------
# API Stage - FastAPI Application
# --------------------------------------------
FROM base as api

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "currency_tracker.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# --------------------------------------------
# Collector Stage - Data Collection Service
# --------------------------------------------
FROM base as collector

USER appuser

CMD ["python", "-m", "currency_tracker.collector.scheduler"]

# --------------------------------------------
# ML Trainer Stage - Model Training Service
# --------------------------------------------
FROM base as ml-trainer

# Install additional ML dependencies
RUN pip install --no-cache-dir optuna shap hyperopt

USER appuser

CMD ["python", "-m", "currency_tracker.ml.training.scheduler"]

# --------------------------------------------
# Alerts Stage - Alert Processing Service
# --------------------------------------------
FROM base as alerts

USER appuser

CMD ["python", "-m", "currency_tracker.alerts.scheduler"]

# --------------------------------------------
# Dashboard Stage - Streamlit Frontend
# --------------------------------------------
FROM base as dashboard

# Install dashboard dependencies
RUN pip install --no-cache-dir streamlit-option-menu streamlit-echarts

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "currency_tracker/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

# --------------------------------------------
# Development Stage - All tools for development
# --------------------------------------------
FROM base as dev

USER root

# Install dev tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    htop \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install dev Python packages
RUN pip install --no-cache-dir \
    pytest pytest-asyncio pytest-cov pytest-mock \
    black ruff mypy pre-commit \
    ipython jupyter

USER appuser

CMD ["sleep", "infinity"]