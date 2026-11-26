from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Index, ForeignKey, UniqueConstraint, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy import Uuid as UUID
import uuid
import enum
Base = declarative_base()

class RateTypeEnum(str, enum.Enum):
    COMMERCIAL = 'commercial'
    TOURISM = 'tourism'
    OFFICIAL = 'official'
    PARALLEL = 'parallel'
    CRYPTO = 'crypto'

class Currency(Base):
    __tablename__ = 'currencies'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(3), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    symbol = Column(String(10))
    symbol_native = Column(String(10))
    decimal_places = Column(Integer, default=4)
    is_base = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    category = Column(String(50))
    priority = Column(String(20))
    volatility = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    rates = relationship('ExchangeRate', foreign_keys='ExchangeRate.quote_currency_id', back_populates='quote_currency_rel')
    base_rates = relationship('ExchangeRate', foreign_keys='ExchangeRate.base_currency_id', back_populates='base_currency_rel')

    def __repr__(self):
        return f'<Currency(code={self.code}, name={self.name})>'

class DataSource(Base):
    __tablename__ = 'data_sources'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100))
    base_url = Column(String(255))
    api_key_required = Column(Boolean, default=False)
    rate_limit_per_second = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    config = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    rates = relationship('ExchangeRate', back_populates='source_rel')

    def __repr__(self):
        return f'<DataSource(name={self.name})>'

class ExchangeRate(Base):
    __tablename__ = 'exchange_rates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    base_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False, index=True)
    quote_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False, index=True)
    rate = Column(Numeric(precision=18, scale=8), nullable=False)
    bid = Column(Numeric(precision=18, scale=8))
    ask = Column(Numeric(precision=18, scale=8))
    spread = Column(Numeric(precision=10, scale=4))
    rate_type = Column(SQLEnum(RateTypeEnum), default=RateTypeEnum.COMMERCIAL)
    source_id = Column(Integer, ForeignKey('data_sources.id'), nullable=False, index=True)
    rate_timestamp = Column(DateTime, nullable=False, index=True)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)
    raw_data = Column(Text)
    base_currency_rel = relationship('Currency', foreign_keys=[base_currency_id], back_populates='base_rates')
    quote_currency_rel = relationship('Currency', foreign_keys=[quote_currency_id], back_populates='rates')
    source_rel = relationship('DataSource', back_populates='rates')
    __table_args__ = (Index('ix_exchange_rates_pair_time', 'base_currency_id', 'quote_currency_id', 'rate_timestamp'), Index('ix_exchange_rates_source_time', 'source_id', 'rate_timestamp'), UniqueConstraint('base_currency_id', 'quote_currency_id', 'source_id', 'rate_timestamp', name='uq_rate_unique'))

    def __repr__(self):
        return f'<ExchangeRate(base={self.base_currency_id}, quote={self.quote_currency_id}, rate={self.rate})>'

class ModelRegistry(Base):
    __tablename__ = 'model_registry'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    model_type = Column(String(50), nullable=False)
    target_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False, index=True)
    base_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False)
    hyperparameters = Column(Text)
    train_mae = Column(Numeric(precision=10, scale=6))
    train_rmse = Column(Numeric(precision=10, scale=6))
    val_mae = Column(Numeric(precision=10, scale=6))
    val_rmse = Column(Numeric(precision=10, scale=6))
    test_mae = Column(Numeric(precision=10, scale=6))
    test_rmse = Column(Numeric(precision=10, scale=6))
    model_path = Column(String(500))
    mlflow_run_id = Column(String(50))
    status = Column(String(20), default='training')
    is_active = Column(Boolean, default=False)
    is_production = Column(Boolean, default=False)
    trained_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    target_currency = relationship('Currency', foreign_keys=[target_currency_id])
    base_currency = relationship('Currency', foreign_keys=[base_currency_id])

    def __repr__(self):
        return f'<ModelRegistry(name={self.name}, version={self.version}, type={self.model_type})>'

class Prediction(Base):
    __tablename__ = 'predictions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    model_id = Column(Integer, ForeignKey('model_registry.id'), nullable=False, index=True)
    base_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False)
    quote_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False)
    prediction_timestamp = Column(DateTime, nullable=False, index=True)
    predicted_rate = Column(Numeric(precision=18, scale=8), nullable=False)
    lower_bound = Column(Numeric(precision=18, scale=8))
    upper_bound = Column(Numeric(precision=18, scale=8))
    confidence_level = Column(Numeric(precision=5, scale=2), default=95.0)
    horizon_days = Column(Integer)
    features_used = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    model = relationship('ModelRegistry')
    base_currency = relationship('Currency', foreign_keys=[base_currency_id])
    quote_currency = relationship('Currency', foreign_keys=[quote_currency_id])
    __table_args__ = (Index('ix_predictions_pair_time', 'base_currency_id', 'quote_currency_id', 'prediction_timestamp'), Index('ix_predictions_model_time', 'model_id', 'prediction_timestamp'))

    def __repr__(self):
        return f'<Prediction(model={self.model_id}, pair={self.base_currency_id}/{self.quote_currency_id}, rate={self.predicted_rate})>'

class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    base_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False)
    quote_currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=False)
    condition_type = Column(String(50), nullable=False)
    threshold_value = Column(Numeric(precision=18, scale=8), nullable=False)
    check_interval_seconds = Column(Integer, default=60)
    cooldown_seconds = Column(Integer, default=3600)
    is_active = Column(Boolean, default=True)
    priority = Column(String(20), default='medium')
    notify_telegram = Column(Boolean, default=False)
    notify_discord = Column(Boolean, default=False)
    notify_email = Column(Boolean, default=False)
    notify_webhook = Column(Boolean, default=False)
    webhook_url = Column(String(500))
    last_triggered = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    base_currency = relationship('Currency', foreign_keys=[base_currency_id])
    quote_currency = relationship('Currency', foreign_keys=[quote_currency_id])

    def __repr__(self):
        return f'<Alert(name={self.name}, pair={self.base_currency_id}/{self.quote_currency_id})>'

class AlertHistory(Base):
    __tablename__ = 'alert_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    alert_id = Column(Integer, ForeignKey('alerts.id'), nullable=False, index=True)
    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    current_rate = Column(Numeric(precision=18, scale=8), nullable=False)
    threshold_value = Column(Numeric(precision=18, scale=8), nullable=False)
    condition_met = Column(String(100))
    telegram_sent = Column(Boolean, default=False)
    discord_sent = Column(Boolean, default=False)
    email_sent = Column(Boolean, default=False)
    webhook_sent = Column(Boolean, default=False)
    alert = relationship('Alert')

    def __repr__(self):
        return f'<AlertHistory(alert={self.alert_id}, rate={self.current_rate})>'
