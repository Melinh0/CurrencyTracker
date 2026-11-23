# ============================================
# CurrencyTracker - Main Package
# ============================================

__version__ = "0.1.0"
__author__ = "CurrencyTracker Team"
__description__ = "Real-time exchange rate monitoring and prediction system"

# Export main modules
from .config import settings, get_settings, get_currency_config
from .collector import CollectorScheduler, source_factory
from .storage import RateRepository, InfluxDBClient
from .ml import (
    TrainingPipeline,
    PredictionService,
    ModelFactory,
    FeatureEngineer
)
from .api import create_app, app
from .dashboard import app as dashboard_app
from .alerts import AlertsScheduler

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "settings",
    "get_settings",
    "get_currency_config",
    "CollectorScheduler",
    "source_factory",
    "RateRepository",
    "InfluxDBClient",
    "TrainingPipeline",
    "PredictionService",
    "ModelFactory",
    "FeatureEngineer",
    "create_app",
    "app",
    "dashboard_app",
    "AlertsScheduler",
]