from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import selectinload, aliased
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import structlog
from currency_tracker.storage.models import Base, Currency, DataSource, ExchangeRate, ModelRegistry, Prediction, Alert, AlertHistory, RateTypeEnum
from currency_tracker.collector.sources import ExchangeRate as CollectorExchangeRate
from currency_tracker.config.settings import get_settings
logger = structlog.get_logger()

class RateRepository:

    def __init__(self, database_url: Optional[str]=None):
        self.settings = get_settings()
        self.database_url = database_url or self.settings.database.url
        self._engine = None
        self._session_factory = None

    async def initialize(self):
        self._engine = create_async_engine(self.database_url, pool_size=self.settings.database.pool_size, max_overflow=self.settings.database.max_overflow, echo=self.settings.database.echo)
        self._session_factory = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info('Database initialized', url=self.database_url)

    @asynccontextmanager
    async def session(self) -> AsyncSession:
        if not self._session_factory:
            await self.initialize()
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def upsert_currency(self, code: str, name: str, **kwargs) -> Currency:
        async with self.session() as session:
            stmt = select(Currency).where(Currency.code == code.upper())
            result = await session.execute(stmt)
            currency = result.scalar_one_or_none()
            if currency:
                for key, value in kwargs.items():
                    if hasattr(currency, key):
                        setattr(currency, key, value)
                currency.updated_at = datetime.utcnow()
            else:
                currency = Currency(code=code.upper(), name=name, **kwargs)
                session.add(currency)
            await session.flush()
            return currency

    async def get_currency(self, code: str) -> Optional[Currency]:
        async with self.session() as session:
            stmt = select(Currency).where(Currency.code == code.upper())
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_currencies(self, active_only: bool=True) -> List[Currency]:
        async with self.session() as session:
            stmt = select(Currency)
            if active_only:
                stmt = stmt.where(Currency.is_active == True)
            stmt = stmt.order_by(Currency.code)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def ensure_currencies_exist(self, currency_codes: List[str]) -> Dict[str, Currency]:
        currencies = {}
        for code in currency_codes:
            currency = await self.get_currency(code)
            if not currency:
                currency = await self.upsert_currency(code, code)
            currencies[code] = currency
        return currencies

    async def upsert_source(self, name: str, display_name: str, **kwargs) -> DataSource:
        async with self.session() as session:
            stmt = select(DataSource).where(DataSource.name == name)
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            if source:
                for key, value in kwargs.items():
                    if hasattr(source, key):
                        setattr(source, key, value)
                source.updated_at = datetime.utcnow()
            else:
                source = DataSource(name=name, display_name=display_name, **kwargs)
                session.add(source)
            await session.flush()
            return source

    async def get_source(self, name: str) -> Optional[DataSource]:
        async with self.session() as session:
            stmt = select(DataSource).where(DataSource.name == name)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_active_sources(self) -> List[DataSource]:
        async with self.session() as session:
            stmt = select(DataSource).where(DataSource.is_active == True).order_by(DataSource.priority.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_rate(self, rate: CollectorExchangeRate) -> ExchangeRate:
        async with self.session() as session:
            currencies = await self.ensure_currencies_exist([rate.base_currency, rate.quote_currency])
            base_currency = currencies[rate.base_currency]
            quote_currency = currencies[rate.quote_currency]
            source = await self.get_source(rate.source)
            if not source:
                source = await self.upsert_source(rate.source, rate.source)
            stmt = select(ExchangeRate).where(and_(ExchangeRate.base_currency_id == base_currency.id, ExchangeRate.quote_currency_id == quote_currency.id, ExchangeRate.source_id == source.id, ExchangeRate.rate_timestamp == rate.timestamp))
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            spread = None
            if rate.bid and rate.ask and (rate.bid > 0):
                spread = (rate.ask - rate.bid) / rate.bid * Decimal('100')
            if existing:
                existing.rate = rate.rate
                existing.bid = rate.bid
                existing.ask = rate.ask
                existing.spread = spread
                existing.rate_type = RateTypeEnum(rate.rate_type.value)
                existing.raw_data = str(rate.raw_data) if rate.raw_data else None
                existing.collected_at = datetime.utcnow()
                db_rate = existing
            else:
                db_rate = ExchangeRate(base_currency_id=base_currency.id, quote_currency_id=quote_currency.id, rate=rate.rate, bid=rate.bid, ask=rate.ask, spread=spread, rate_type=RateTypeEnum(rate.rate_type.value), source_id=source.id, rate_timestamp=rate.timestamp, raw_data=str(rate.raw_data) if rate.raw_data else None)
                session.add(db_rate)
            await session.flush()
            return db_rate

    async def get_latest_rate(self, base: str, quote: str, source: Optional[str]=None) -> Optional[ExchangeRate]:
        async with self.session() as session:
            base_currency = aliased(Currency, name='base_currency')
            quote_currency = aliased(Currency, name='quote_currency')
            stmt = select(ExchangeRate).options(selectinload(ExchangeRate.base_currency_rel), selectinload(ExchangeRate.quote_currency_rel), selectinload(ExchangeRate.source_rel)).join(base_currency, ExchangeRate.base_currency_id == base_currency.id).join(quote_currency, ExchangeRate.quote_currency_id == quote_currency.id, isouter=True).where(and_(base_currency.code == base.upper(), quote_currency.code == quote.upper())).order_by(desc(ExchangeRate.rate_timestamp))
            if source:
                stmt = stmt.join(DataSource).where(DataSource.name == source)
            stmt = stmt.limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_rates_history(self, base: str, quote: str, start_date: datetime, end_date: Optional[datetime]=None, source: Optional[str]=None, limit: int=1000) -> List[ExchangeRate]:
        async with self.session() as session:
            base_currency = aliased(Currency, name='base_currency')
            quote_currency = aliased(Currency, name='quote_currency')
            stmt = select(ExchangeRate).options(selectinload(ExchangeRate.base_currency_rel), selectinload(ExchangeRate.quote_currency_rel), selectinload(ExchangeRate.source_rel)).join(base_currency, ExchangeRate.base_currency_id == base_currency.id).join(quote_currency, ExchangeRate.quote_currency_id == quote_currency.id, isouter=True).where(and_(base_currency.code == base.upper(), quote_currency.code == quote.upper(), ExchangeRate.rate_timestamp >= start_date))
            if end_date:
                stmt = stmt.where(ExchangeRate.rate_timestamp <= end_date)
            if source:
                stmt = stmt.join(DataSource).where(DataSource.name == source)
            stmt = stmt.order_by(ExchangeRate.rate_timestamp).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_rates_all_pairs(self, base: str, sources: Optional[List[str]]=None) -> List[ExchangeRate]:
        async with self.session() as session:
            subq = select(ExchangeRate.base_currency_id, ExchangeRate.quote_currency_id, ExchangeRate.source_id, func.max(ExchangeRate.rate_timestamp).label('max_ts')).join(Currency, ExchangeRate.base_currency_id == Currency.id).where(Currency.code == base.upper()).group_by(ExchangeRate.base_currency_id, ExchangeRate.quote_currency_id, ExchangeRate.source_id).subquery()
            stmt = select(ExchangeRate).options(selectinload(ExchangeRate.base_currency_rel), selectinload(ExchangeRate.quote_currency_rel), selectinload(ExchangeRate.source_rel)).join(subq, and_(ExchangeRate.base_currency_id == subq.c.base_currency_id, ExchangeRate.quote_currency_id == subq.c.quote_currency_id, ExchangeRate.source_id == subq.c.source_id, ExchangeRate.rate_timestamp == subq.c.max_ts))
            if sources:
                stmt = stmt.join(DataSource).where(DataSource.name.in_(sources))
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_statistics(self, base: str, quote: str, days: int=30) -> Dict[str, Any]:
        async with self.session() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            base_currency = aliased(Currency, name='base_currency')
            quote_currency = aliased(Currency, name='quote_currency')
            stmt = select(ExchangeRate.rate, ExchangeRate.spread).join(base_currency, ExchangeRate.base_currency_id == base_currency.id).join(quote_currency, ExchangeRate.quote_currency_id == quote_currency.id, isouter=True).where(and_(base_currency.code == base.upper(), quote_currency.code == quote.upper(), ExchangeRate.rate_timestamp >= start_date))
            result = await session.execute(stmt)
            rows = result.all()
            if not rows:
                return {'pair': f'{base}/{quote}', 'period_days': days, 'count': 0, 'avg_rate': None, 'min_rate': None, 'max_rate': None, 'stddev_rate': None, 'avg_spread': None}
            rates = [float(r[0]) for r in rows]
            spreads = [float(r[1]) for r in rows if r[1] is not None]
            count = len(rates)
            avg_rate = sum(rates) / count
            min_rate = min(rates)
            max_rate = max(rates)
            variance = sum(((r - avg_rate) ** 2 for r in rates)) / count
            stddev_rate = variance ** 0.5
            avg_spread = sum(spreads) / len(spreads) if spreads else None
            return {'pair': f'{base}/{quote}', 'period_days': days, 'count': count, 'avg_rate': avg_rate, 'min_rate': min_rate, 'max_rate': max_rate, 'stddev_rate': stddev_rate, 'avg_spread': avg_spread}

    async def set_active_model(self, name, target_code, base_code, model_path, meta):
        currencies = await self.ensure_currencies_exist([base_code, target_code])
        base_id = currencies[base_code.upper()].id
        tgt_id = currencies[target_code.upper()].id
        async with self.session() as session:
            existing = await session.execute(select(ModelRegistry).where(and_(ModelRegistry.target_currency_id == tgt_id, ModelRegistry.base_currency_id == base_id)))
            for m in existing.scalars().all():
                m.is_active = False
                m.is_production = False
            import json as _json
            reg = ModelRegistry(name=name, version='1', model_type='ridge', target_currency_id=tgt_id, base_currency_id=base_id, hyperparameters=_json.dumps(meta), model_path=model_path, status='ready', is_active=True, is_production=True, trained_at=datetime.utcnow())
            session.add(reg)
            await session.flush()
            return reg

    async def save_model(self, model: ModelRegistry) -> ModelRegistry:
        async with self.session() as session:
            session.add(model)
            await session.flush()
            return model

    async def get_model(self, model_id: int) -> Optional[ModelRegistry]:
        async with self.session() as session:
            stmt = select(ModelRegistry).where(ModelRegistry.id == model_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_active_model(self, target_currency: str, base_currency: str='BRL') -> Optional[ModelRegistry]:
        async with self.session() as session:
            BaseCurr = aliased(Currency)
            TargetCurr = aliased(Currency)
            stmt = select(ModelRegistry).join(BaseCurr, ModelRegistry.base_currency_id == BaseCurr.id).join(TargetCurr, ModelRegistry.target_currency_id == TargetCurr.id).where(and_(BaseCurr.code == base_currency.upper(), TargetCurr.code == target_currency.upper(), ModelRegistry.is_active == True, ModelRegistry.status == 'ready')).order_by(desc(ModelRegistry.trained_at)).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_models_for_currency(self, target_currency: str) -> List[ModelRegistry]:
        async with self.session() as session:
            TargetCurr = aliased(Currency)
            stmt = select(ModelRegistry).join(TargetCurr, ModelRegistry.target_currency_id == TargetCurr.id).where(TargetCurr.code == target_currency.upper()).order_by(desc(ModelRegistry.trained_at))
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_prediction(self, prediction: Prediction) -> Prediction:
        async with self.session() as session:
            session.add(prediction)
            await session.flush()
            return prediction

    async def get_predictions(self, base: str, quote: str, model_id: Optional[int]=None, limit: int=100) -> List[Prediction]:
        async with self.session() as session:
            stmt = select(Prediction).join(Currency, Prediction.base_currency_id == Currency.id).join(Currency, Prediction.quote_currency_id == Currency.id, isouter=True).where(and_(Currency.code == base.upper(), Currency.code == quote.upper()))
            if model_id:
                stmt = stmt.where(Prediction.model_id == model_id)
            stmt = stmt.order_by(desc(Prediction.prediction_timestamp)).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_alert(self, alert: Alert) -> Alert:
        async with self.session() as session:
            session.add(alert)
            await session.flush()
            return alert

    async def get_active_alerts(self) -> List[Alert]:
        async with self.session() as session:
            stmt = select(Alert).where(Alert.is_active == True)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_alert_history(self, history: AlertHistory) -> AlertHistory:
        async with self.session() as session:
            session.add(history)
            await session.flush()
            return history
