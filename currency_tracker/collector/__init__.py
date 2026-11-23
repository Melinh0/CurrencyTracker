# ============================================
# CurrencyTracker - Collector Package
# ============================================

from .scheduler import CollectorScheduler, CollectionJob, main
from .factory import source_factory, SourceFactory
from .validator import RateValidator, CrossSourceValidator, ValidationResult
from .sources import (
    BaseSource,
    ExchangeRate,
    CollectionResult,
    RateType,
    AwesomeAPISource,
    ExchangeRateAPISource,
    AlphaVantageSource,
    BCBSource,
    YahooFinanceSource,
    TwelveDataSource,
)

__all__ = [
    "CollectorScheduler",
    "CollectionJob",
    "main",
    "source_factory",
    "SourceFactory",
    "RateValidator",
    "CrossSourceValidator",
    "ValidationResult",
    "BaseSource",
    "ExchangeRate",
    "CollectionResult",
    "RateType",
    "AwesomeAPISource",
    "ExchangeRateAPISource",
    "AlphaVantageSource",
    "BCBSource",
    "YahooFinanceSource",
    "TwelveDataSource",
]