# ============================================
# CurrencyTracker - Repository Layer
# ============================================

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload
import structlog

from currency_tracker.storage.models import (
    Base, Currency, DataSource, ExchangeRate, ModelRegistry,
    Prediction, Alert, AlertHistory, RateTypeEnum
)
from currency_tracker.collector.sources import ExchangeRate as CollectorExchangeRate
from currency_tracker.config.settings import get_settings

logger = structlog.get_logger()


class RateRepository:
    """Repositório para operações de taxas de câmbio"""

    def __init__(self, database_url: Optional[str] = None):
        self.settings = get_settings()
        self.database_url = database_url or self.settings.database.url
        self._engine = None
        self._session_factory = None

    async def initialize(self):
        """Inicializa engine e cria tabelas"""
        self._engine = create_async_engine(
            self.database_url,
            pool_size=self.settings.database.pool_size,
            max_overflow=self.settings.database.max_overflow,
            echo=self.settings.database.echo,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Cria tabelas se não existirem
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized", url=self.database_url)

    @asynccontextmanager
    async def session(self) -> AsyncSession:
        """Context manager para sessão"""
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
        """Fecha conexões"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    # ============================================
    # Currency Operations
    # ============================================

    async def upsert_currency(self, code: str, name: str, **kwargs) -> Currency:
        """Insere ou atualiza moeda"""
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
        """Busca moeda por código"""
        async with self.session() as session:
            stmt = select(Currency).where(Currency.code == code.upper())
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_currencies(self, active_only: bool = True) -> List[Currency]:
        """Lista todas as moedas"""
        async with self.session() as session:
            stmt = select(Currency)
            if active_only:
                stmt = stmt.where(Currency.is_active == True)
            stmt = stmt.order_by(Currency.code)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def ensure_currencies_exist(self, currency_codes: List[str]) -> Dict[str, Currency]:
        """Garante que moedas existam no banco"""
        currencies = {}
        for code in currency_codes:
            currency = await self.get_currency(code)
            if not currency:
                currency = await self.upsert_currency(code, code)
            currencies[code] = currency
        return currencies

    # ============================================
    # DataSource Operations
    # ============================================

    async def upsert_source(self, name: str, display_name: str, **kwargs) -> DataSource:
        """Insere ou atualiza fonte de dados"""
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
        """Busca fonte por nome"""
        async with self.session() as session:
            stmt = select(DataSource).where(DataSource.name == name)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_active_sources(self) -> List[DataSource]:
        """Lista fontes ativas"""
        async with self.session() as session:
            stmt = select(DataSource).where(DataSource.is_active == True).order_by(DataSource.priority.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ============================================
    # ExchangeRate Operations
    # ============================================

    async def save_rate(self, rate: CollectorExchangeRate) -> ExchangeRate:
        """Salva taxa de câmbio"""
        async with self.session() as session:
            # Garante moedas e fonte existam
            currencies = await self.ensure_currencies_exist([rate.base_currency, rate.quote_currency])
            base_currency = currencies[rate.base_currency]
            quote_currency = currencies[rate.quote_currency]

            source = await self.get_source(rate.source)
            if not source:
                source = await self.upsert_source(rate.source, rate.source)

            # Verifica se já existe (mesmo par, fonte, timestamp)
            stmt = select(ExchangeRate).where(
                and_(
                    ExchangeRate.base_currency_id == base_currency.id,
                    ExchangeRate.quote_currency_id == quote_currency.id,
                    ExchangeRate.source_id == source.id,
                    ExchangeRate.rate_timestamp == rate.timestamp
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            spread = None
            if rate.bid and rate.ask and rate.bid > 0:
                spread = ((rate.ask - rate.bid) / rate.bid) * Decimal("100")

            if existing:
                # Atualiza
                existing.rate = rate.rate
                existing.bid = rate.bid
                existing.ask = rate.ask
                existing.spread = spread
                existing.rate_type = RateTypeEnum(rate.rate_type.value)
                existing.raw_data = str(rate.raw_data) if rate.raw_data else None
                existing.collected_at = datetime.utcnow()
                db_rate = existing
            else:
                # Insere novo
                db_rate = ExchangeRate(
                    base_currency_id=base_currency.id,
                    quote_currency_id=quote_currency.id,
                    rate=rate.rate,
                    bid=rate.bid,
                    ask=rate.ask,
                    spread=spread,
                    rate_type=RateTypeEnum(rate.rate_type.value),
                    source_id=source.id,
                    rate_timestamp=rate.timestamp,
                    raw_data=str(rate.raw_data) if rate.raw_data else None
                )
                session.add(db_rate)

            await session.flush()
            return db_rate

    async def get_latest_rate(
        self,
        base: str,
        quote: str,
        source: Optional[str] = None
    ) -> Optional[ExchangeRate]:
        """Busca taxa mais recente"""
        async with self.session() as session:
            stmt = select(ExchangeRate).join(Currency, ExchangeRate.base_currency_id == Currency.id).join(
                Currency, ExchangeRate.quote_currency_id == Currency.id, isouter=True
            ).where(
                and_(
                    Currency.code == base.upper(),
                    Currency.code == quote.upper()
                )
            ).order_by(desc(ExchangeRate.rate_timestamp))

            if source:
                stmt = stmt.join(DataSource).where(DataSource.name == source)

            stmt = stmt.limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_rates_history(
        self,
        base: str,
        quote: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        source: Optional[str] = None,
        limit: int = 1000
    ) -> List[ExchangeRate]:
        """Busca histórico de taxas"""
        async with self.session() as session:
            stmt = select(ExchangeRate).join(
                Currency, ExchangeRate.base_currency_id == Currency.id
            ).join(
                Currency, ExchangeRate.quote_currency_id == Currency.id, isouter=True
            ).where(
                and_(
                    Currency.code == base.upper(),
                    Currency.code == quote.upper(),
                    ExchangeRate.rate_timestamp >= start_date
                )
            )

            if end_date:
                stmt = stmt.where(ExchangeRate.rate_timestamp <= end_date)

            if source:
                stmt = stmt.join(DataSource).where(DataSource.name == source)

            stmt = stmt.order_by(desc(ExchangeRate.rate_timestamp)).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_rates_all_pairs(
        self,
        base: str,
        sources: Optional[List[str]] = None
    ) -> List[ExchangeRate]:
        """Busca taxas mais recentes para todos os pares de uma base"""
        async with self.session() as session:
            # Subquery para pegar o máximo timestamp por par
            subq = select(
                ExchangeRate.base_currency_id,
                ExchangeRate.quote_currency_id,
                ExchangeRate.source_id,
                func.max(ExchangeRate.rate_timestamp).label("max_ts")
            ).join(
                Currency, ExchangeRate.base_currency_id == Currency.id
            ).where(
                Currency.code == base.upper()
            ).group_by(
                ExchangeRate.base_currency_id,
                ExchangeRate.quote_currency_id,
                ExchangeRate.source_id
            ).subquery()

            stmt = select(ExchangeRate).join(
                subq,
                and_(
                    ExchangeRate.base_currency_id == subq.c.base_currency_id,
                    ExchangeRate.quote_currency_id == subq.c.quote_currency_id,
                    ExchangeRate.source_id == subq.c.source_id,
                    ExchangeRate.rate_timestamp == subq.c.max_ts
                )
            )

            if sources:
                stmt = stmt.join(DataSource).where(DataSource.name.in_(sources))

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_statistics(
        self,
        base: str,
        quote: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Calcula estatísticas para um par"""
        async with self.session() as session:
            start_date = datetime.utcnow() - timedelta(days=days)

            stmt = select(
                func.count(ExchangeRate.id).label("count"),
                func.avg(ExchangeRate.rate).label("avg_rate"),
                func.min(ExchangeRate.rate).label("min_rate"),
                func.max(ExchangeRate.rate).label("max_rate"),
                func.stddev(ExchangeRate.rate).label("stddev_rate"),
                func.avg(ExchangeRate.spread).label("avg_spread")
            ).join(
                Currency, ExchangeRate.base_currency_id == Currency.id
            ).join(
                Currency, ExchangeRate.quote_currency_id == Currency.id, isouter=True
            ).where(
                and_(
                    Currency.code == base.upper(),
                    Currency.code == quote.upper(),
                    ExchangeRate.rate_timestamp >= start_date
                )
            )

            result = await session.execute(stmt)
            row = result.one()

            return {
                "pair": f"{base}/{quote}",
                "period_days": days,
                "count": row.count or 0,
                "avg_rate": float(row.avg_rate) if row.avg_rate else None,
                "min_rate": float(row.min_rate) if row.min_rate else None,
                "max_rate": float(row.max_rate) if row.max_rate else None,
                "stddev_rate": float(row.stddev_rate) if row.stddev_rate else None,
                "avg_spread": float(row.avg_spread) if row.avg_spread else None,
            }

    # ============================================
    # ModelRegistry Operations
    # ============================================

    async def save_model(self, model: ModelRegistry) -> ModelRegistry:
        """Salva modelo no registry"""
        async with self.session() as session:
            session.add(model)
            await session.flush()
            return model

    async def get_model(self, model_id: int) -> Optional[ModelRegistry]:
        """Busca modelo por ID"""
        async with self.session() as session:
            stmt = select(ModelRegistry).where(ModelRegistry.id == model_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_active_model(self, target_currency: str, base_currency: str = "BRL") -> Optional[ModelRegistry]:
        """Busca modelo ativo para um par"""
        async with self.session() as session:
            stmt = select(ModelRegistry).join(
                Currency, ModelRegistry.target_currency_id == Currency.id
            ).join(
                Currency, ModelRegistry.base_currency_id == Currency.id, isouter=True
            ).where(
                and_(
                    Currency.code == target_currency.upper(),
                    Currency.code == base_currency.upper(),
                    ModelRegistry.is_active == True,
                    ModelRegistry.status == "ready"
                )
            ).order_by(desc(ModelRegistry.trained_at)).limit(1)

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_models_for_currency(self, target_currency: str) -> List[ModelRegistry]:
        """Lista todos os modelos para uma moeda"""
        async with self.session() as session:
            stmt = select(ModelRegistry).join(
                Currency, ModelRegistry.target_currency_id == Currency.id
            ).where(
                Currency.code == target_currency.upper()
            ).order_by(desc(ModelRegistry.trained_at))

            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ============================================
    # Prediction Operations
    # ============================================

    async def save_prediction(self, prediction: Prediction) -> Prediction:
        """Salva previsão"""
        async with self.session() as session:
            session.add(prediction)
            await session.flush()
            return prediction

    async def get_predictions(
        self,
        base: str,
        quote: str,
        model_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Prediction]:
        """Busca previsões"""
        async with self.session() as session:
            stmt = select(Prediction).join(
                Currency, Prediction.base_currency_id == Currency.id
            ).join(
                Currency, Prediction.quote_currency_id == Currency.id, isouter=True
            ).where(
                and_(
                    Currency.code == base.upper(),
                    Currency.code == quote.upper()
                )
            )

            if model_id:
                stmt = stmt.where(Prediction.model_id == model_id)

            stmt = stmt.order_by(desc(Prediction.prediction_timestamp)).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ============================================
    # Alert Operations
    # ============================================

    async def save_alert(self, alert: Alert) -> Alert:
        """Salva alerta"""
        async with self.session() as session:
            session.add(alert)
            await session.flush()
            return alert

    async def get_active_alerts(self) -> List[Alert]:
        """Lista alertas ativos"""
        async with self.session() as session:
            stmt = select(Alert).where(Alert.is_active == True)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_alert_history(self, history: AlertHistory) -> AlertHistory:
        """Salva histórico de alerta"""
        async with self.session() as session:
            session.add(history)
            await session.flush()
            return history