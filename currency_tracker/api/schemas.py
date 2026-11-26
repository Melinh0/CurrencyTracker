from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class RateType(str, Enum):
    COMMERCIAL = 'commercial'
    TOURISM = 'tourism'
    OFFICIAL = 'official'
    PARALLEL = 'parallel'
    CRYPTO = 'crypto'

class CurrencyBase(BaseModel):
    code: str = Field(..., min_length=3, max_length=3, pattern='^[A-Z]{3}$')
    name: str
    symbol: Optional[str] = None
    symbol_native: Optional[str] = None
    decimal_places: int = 4
    is_base: bool = False
    category: Optional[str] = None
    priority: Optional[str] = None

class CurrencyResponse(CurrencyBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DataSourceBase(BaseModel):
    name: str
    display_name: str
    base_url: Optional[str] = None
    api_key_required: bool = False
    rate_limit_per_second: int = 10
    priority: int = 0

class DataSourceResponse(DataSourceBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ExchangeRateBase(BaseModel):
    base_currency: str
    quote_currency: str
    rate: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    rate_type: RateType = RateType.COMMERCIAL
    source: str

class ExchangeRateResponse(ExchangeRateBase):
    id: int
    spread: Optional[Decimal] = None
    rate_timestamp: datetime
    collected_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ExchangeRateLatest(BaseModel):
    base: str
    quote: str
    rate: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None
    source: str
    timestamp: datetime

class RateHistoryQuery(BaseModel):
    base: str = Field(..., pattern='^[A-Z]{3}$')
    quote: str = Field(..., pattern='^[A-Z]{3}$')
    start_date: datetime
    end_date: Optional[datetime] = None
    source: Optional[str] = None
    limit: int = Field(default=100, le=10000)

class RateStatistics(BaseModel):
    pair: str
    period_days: int
    count: int
    avg_rate: Optional[float] = None
    min_rate: Optional[float] = None
    max_rate: Optional[float] = None
    stddev_rate: Optional[float] = None
    avg_spread: Optional[float] = None

class PredictionRequest(BaseModel):
    base: str = Field(..., pattern='^[A-Z]{3}$')
    quote: str = Field(..., pattern='^[A-Z]{3}$')
    horizon_days: int = Field(default=7, ge=1, le=90)
    model_name: Optional[str] = None
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.99)

class PredictionPoint(BaseModel):
    day: int
    date: str
    predicted_rate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float

class PredictionResponse(BaseModel):
    base: str
    quote: str
    model: str
    horizon_days: int
    confidence_level: float
    predictions: List[PredictionPoint]
    generated_at: str

class ModelConfigRequest(BaseModel):
    name: str
    model_type: str
    hyperparameters: Dict[str, Any] = {}
    target_currency: str
    base_currency: str = 'BRL'
    feature_columns: Optional[List[str]] = None
    prediction_horizon: int = 1

class ModelResponse(BaseModel):
    id: int
    uuid: str
    name: str
    version: str
    model_type: str
    target_currency: str
    base_currency: str
    hyperparameters: Dict[str, Any]
    train_mae: Optional[float] = None
    train_rmse: Optional[float] = None
    val_mae: Optional[float] = None
    val_rmse: Optional[float] = None
    test_mae: Optional[float] = None
    test_rmse: Optional[float] = None
    status: str
    is_active: bool
    is_production: bool
    trained_at: datetime
    deployed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class TrainingRequest(BaseModel):
    target_currency: str = Field(..., pattern='^[A-Z]{3}$')
    base_currency: str = Field(default='BRL', pattern='^[A-Z]{3}$')
    model_types: Optional[List[str]] = None
    prediction_horizon: int = Field(default=1, ge=1, le=30)
    lookback_days: int = Field(default=365, ge=30, le=3650)
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)
    min_training_samples: int = Field(default=100, ge=50)

class TrainingResponse(BaseModel):
    target_currency: str
    base_currency: str
    data_samples: int
    feature_count: int
    models_trained: List[str]
    test_results: Dict[str, Dict[str, float]]
    best_model: Optional[str] = None
    ensemble: bool = False
    timestamp: str

class AlertBase(BaseModel):
    name: str
    description: Optional[str] = None
    base_currency: str = Field(..., pattern='^[A-Z]{3}$')
    quote_currency: str = Field(..., pattern='^[A-Z]{3}$')
    condition_type: str = Field(..., pattern='^(above|below|change_pct|volatility)$')
    threshold_value: Decimal
    check_interval_seconds: int = Field(default=60, ge=10)
    cooldown_seconds: int = Field(default=3600, ge=60)
    priority: str = Field(default='medium', pattern='^(low|medium|high|critical)$')
    notify_telegram: bool = False
    notify_discord: bool = False
    notify_email: bool = False
    notify_webhook: bool = False
    webhook_url: Optional[str] = None

class AlertResponse(AlertBase):
    id: int
    uuid: str
    is_active: bool
    last_triggered: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, bool]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
