# ============================================
# CurrencyTracker - API Package
# ============================================

from .main import create_app, app
from .schemas import (
    ExchangeRateLatest,
    RateHistoryQuery,
    RateStatistics,
    PredictionRequest,
    PredictionResponse,
    TrainingRequest,
    TrainingResponse,
    ModelResponse,
    AlertBase,
    AlertResponse,
    HealthResponse,
    ErrorResponse,
    CurrencyResponse,
    DataSourceResponse,
)
from .dependencies import get_rate_repo, get_influxdb, get_current_user, require_roles

__all__ = [
    "create_app",
    "app",
    "ExchangeRateLatest",
    "RateHistoryQuery",
    "RateStatistics",
    "PredictionRequest",
    "PredictionResponse",
    "TrainingRequest",
    "TrainingResponse",
    "ModelResponse",
    "AlertBase",
    "AlertResponse",
    "HealthResponse",
    "ErrorResponse",
    "CurrencyResponse",
    "DataSourceResponse",
    "get_rate_repo",
    "get_influxdb",
    "get_current_user",
    "require_roles",
]