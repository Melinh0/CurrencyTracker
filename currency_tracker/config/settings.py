# ============================================
# CurrencyTracker - Configurações Centrais
# ============================================

from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class DatabaseSettings(BaseSettings):
    """Configurações de banco de dados"""
    url: str = Field(default="postgresql://currency_user:currency_pass@localhost:5432/currency_tracker", alias="DATABASE_URL")
    pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    echo: bool = Field(default=False, alias="DB_ECHO")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class InfluxDBSettings(BaseSettings):
    """Configurações do InfluxDB"""
    url: str = Field(default="http://localhost:8086", alias="INFLUXDB_URL")
    token: str = Field(default="", alias="INFLUXDB_TOKEN")
    org: str = Field(default="currency-tracker", alias="INFLUXDB_ORG")
    bucket: str = Field(default="rates", alias="INFLUXDB_BUCKET")
    bucket_predictions: str = Field(default="predictions", alias="INFLUXDB_BUCKET_PREDICTIONS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class RedisSettings(BaseSettings):
    """Configurações do Redis"""
    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    ttl_seconds: int = Field(default=60, alias="REDIS_TTL_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class APIKeysSettings(BaseSettings):
    """Chaves de API externas"""
    awesome_api_key: str = Field(default="", alias="AWESOME_API_KEY")
    exchange_rate_api_key: str = Field(default="", alias="EXCHANGE_RATE_API_KEY")
    alpha_vantage_api_key: str = Field(default="", alias="ALPHA_VANTAGE_API_KEY")
    twelve_data_api_key: str = Field(default="", alias="TWELVE_DATA_API_KEY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class MLSettings(BaseSettings):
    """Configurações de Machine Learning"""
    mlflow_tracking_uri: str = Field(default="http://localhost:5000", alias="MLFLOW_TRACKING_URI")
    mlflow_experiment_name: str = Field(default="currency-prediction", alias="MLFLOW_EXPERIMENT_NAME")
    model_registry_path: str = Field(default="./models/registry", alias="MODEL_REGISTRY_PATH")
    default_prediction_horizon_days: int = Field(default=7, alias="DEFAULT_PREDICTION_HORIZON_DAYS")
    retrain_interval_hours: int = Field(default=24, alias="RETRAIN_INTERVAL_HOURS")
    min_training_samples: int = Field(default=100, alias="MIN_TRAINING_SAMPLES")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AlertSettings(BaseSettings):
    """Configurações de Alertas"""
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    telegram_enabled: bool = Field(default=False, alias="TELEGRAM_ENABLED")

    discord_webhook_url: str = Field(default="", alias="DISCORD_WEBHOOK_URL")
    discord_enabled: bool = Field(default=False, alias="DISCORD_ENABLED")

    email_smtp_host: str = Field(default="smtp.gmail.com", alias="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=587, alias="EMAIL_SMTP_PORT")
    email_user: str = Field(default="", alias="EMAIL_USER")
    email_password: str = Field(default="", alias="EMAIL_PASSWORD")
    email_from: str = Field(default="CurrencyTracker <noreply@currencytracker.local>", alias="EMAIL_FROM")
    email_enabled: bool = Field(default=False, alias="EMAIL_ENABLED")

    alert_webhook_url: str = Field(default="", alias="ALERT_WEBHOOK_URL")
    alert_webhook_secret: str = Field(default="", alias="ALERT_WEBHOOK_SECRET")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class SchedulerSettings(BaseSettings):
    """Configurações do Scheduler"""
    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")
    celery_timezone: str = Field(default="America/Sao_Paulo", alias="CELERY_TIMEZONE")
    collection_interval_seconds: int = Field(default=60, alias="COLLECTION_INTERVAL_SECONDS")
    health_check_interval_seconds: int = Field(default=300, alias="HEALTH_CHECK_INTERVAL_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class FeatureFlags(BaseSettings):
    """Feature Flags"""
    enable_websocket_collector: bool = Field(default=False, alias="ENABLE_WEBSOCKET_COLLECTOR")
    enable_ml_predictions: bool = Field(default=True, alias="ENABLE_ML_PREDICTIONS")
    enable_alerts: bool = Field(default=True, alias="ENABLE_ALERTS")
    enable_dashboard: bool = Field(default=True, alias="ENABLE_DASHBOARD")
    enable_api_docs: bool = Field(default=True, alias="ENABLE_API_DOCS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppSettings(BaseSettings):
    """Configurações principais da aplicação"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # App
    app_name: str = Field(default="CurrencyTracker", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="", alias="SECRET_KEY")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    # Moedas
    base_currency: str = Field(default="BRL", alias="BASE_CURRENCY")
    tracked_currencies: str = Field(default="USD,EUR,GBP,JPY,RUB,ARS,CLP,COP,MXN,CNY,INR,ZAR,AUD,CAD,CHF", alias="TRACKED_CURRENCIES")

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    influxdb: InfluxDBSettings = InfluxDBSettings()
    redis: RedisSettings = RedisSettings()
    api_keys: APIKeysSettings = APIKeysSettings()
    ml: MLSettings = MLSettings()
    alerts: AlertSettings = AlertSettings()
    scheduler: SchedulerSettings = SchedulerSettings()
    features: FeatureFlags = FeatureFlags()

    @field_validator("tracked_currencies", mode="before")
    @classmethod
    def parse_tracked_currencies(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [c.strip().upper() for c in v.split(",") if c.strip()]
        return [c.upper() for c in v]

    @property
    def tracked_currency_list(self) -> List[str]:
        """Lista de moedas monitoradas (excluindo a base)"""
        return [c for c in self.tracked_currencies if c != self.base_currency]


class CurrencyConfig:
    """Configuração detalhada de moedas a partir do YAML"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent / "currencies.yaml"
        self._config = self._load_config()

    def _load_config(self) -> dict:
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def base_currency(self) -> str:
        return self._config.get("base_currency", "BRL")

    @property
    def currencies(self) -> List[dict]:
        return self._config.get("tracked_currencies", [])

    def get_currency(self, code: str) -> Optional[dict]:
        for c in self.currencies:
            if c["code"].upper() == code.upper():
                return c
        return None

    def get_currencies_by_priority(self, priority: str) -> List[dict]:
        return [c for c in self.currencies if c.get("priority") == priority]

    def get_currencies_by_category(self, category: str) -> List[dict]:
        return [c for c in self.currencies if c.get("category") == category]

    def get_sources_for_currency(self, code: str) -> List[str]:
        currency = self.get_currency(code)
        if currency:
            return currency.get("sources", [])
        return []

    @property
    def collection_config(self) -> dict:
        return self._config.get("collection", {})

    @property
    def validation_config(self) -> dict:
        return self._config.get("validation", {})

    @property
    def storage_config(self) -> dict:
        return self._config.get("storage", {})


@lru_cache()
def get_settings() -> AppSettings:
    """Retorna instância singleton das configurações"""
    return AppSettings()


@lru_cache()
def get_currency_config() -> CurrencyConfig:
    """Retorna instância singleton da configuração de moedas"""
    return CurrencyConfig()