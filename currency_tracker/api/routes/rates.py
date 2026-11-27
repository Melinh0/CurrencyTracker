# ============================================
# CurrencyTracker - Rates API Routes
# ============================================

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_cache.decorator import cache

from currency_tracker.api.schemas import (
    ExchangeRateLatest,
    RateHistoryQuery,
    RateStatistics,
    CurrencyResponse,
    DataSourceResponse,
    ErrorResponse,
    PaginatedResponse
)
from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.influxdb_client import InfluxDBClient
from currency_tracker.config.settings import get_settings
from currency_tracker.api.dependencies import get_rate_repo, get_influxdb

router = APIRouter(prefix="/rates", tags=["Exchange Rates"])


@router.get(
    "/latest",
    response_model=List[ExchangeRateLatest],
    summary="Get latest exchange rates",
    description="Returns the most recent exchange rate for each tracked currency pair"
)
async def get_latest_rates(
    base: str = Query(default="BRL", pattern="^[A-Z]{3}$", description="Base currency"),
    sources: Optional[List[str]] = Query(default=None, description="Filter by sources"),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca taxas mais recentes para todos os pares de uma moeda base"""
    rates = await repo.get_latest_rates_all_pairs(base, sources)

    result = []
    for r in rates:
        base_cur = r.base_currency_rel.code if r.base_currency_rel else base
        quote_cur = r.quote_currency_rel.code if r.quote_currency_rel else "UNKNOWN"
        source_name = r.source_rel.name if r.source_rel else "unknown"

        spread = float(r.spread) if r.spread else None
        if r.bid and r.ask and r.bid > 0:
            spread = float((r.ask - r.bid) / r.bid * 100)

        result.append(ExchangeRateLatest(
            base=base_cur,
            quote=quote_cur,
            rate=float(r.rate),
            bid=float(r.bid) if r.bid else None,
            ask=float(r.ask) if r.ask else None,
            spread=spread,
            source=source_name,
            timestamp=r.rate_timestamp
        ))

    return result


@router.get(
    "/latest/{quote}",
    response_model=ExchangeRateLatest,
    summary="Get latest rate for specific pair",
    description="Returns the most recent exchange rate for a specific currency pair"
)
async def get_latest_rate(
    quote: str,
    base: str = Query(default="BRL", pattern="^[A-Z]{3}$"),
    source: Optional[str] = Query(default=None),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca taxa mais recente para um par específico"""
    rate = await repo.get_latest_rate(base, quote, source)

    if not rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rate found for {base}/{quote}"
        )

    base_cur = rate.base_currency_rel.code if rate.base_currency_rel else base
    quote_cur = rate.quote_currency_rel.code if rate.quote_currency_rel else quote
    source_name = rate.source_rel.name if rate.source_rel else "unknown"

    spread = float(rate.spread) if rate.spread else None
    if rate.bid and rate.ask and rate.bid > 0:
        spread = float((rate.ask - rate.bid) / rate.bid * 100)

    return ExchangeRateLatest(
        base=base_cur,
        quote=quote_cur,
        rate=float(rate.rate),
        bid=float(rate.bid) if rate.bid else None,
        ask=float(rate.ask) if rate.ask else None,
        spread=spread,
        source=source_name,
        timestamp=rate.rate_timestamp
    )


@router.post(
    "/history",
    response_model=List[ExchangeRateLatest],
    summary="Get historical rates",
    description="Returns historical exchange rates for a currency pair within a date range"
)
async def get_rates_history(
    query: RateHistoryQuery,
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca histórico de taxas"""
    rates = await repo.get_rates_history(
        base=query.base,
        quote=query.quote,
        start_date=query.start_date,
        end_date=query.end_date,
        source=query.source,
        limit=query.limit
    )

    result = []
    for r in rates:
        base_cur = r.base_currency_rel.code if r.base_currency_rel else query.base
        quote_cur = r.quote_currency_rel.code if r.quote_currency_rel else query.quote
        source_name = r.source_rel.name if r.source_rel else "unknown"

        spread = float(r.spread) if r.spread else None
        if r.bid and r.ask and r.bid > 0:
            spread = float((r.ask - r.bid) / r.bid * 100)

        result.append(ExchangeRateLatest(
            base=base_cur,
            quote=quote_cur,
            rate=float(r.rate),
            bid=float(r.bid) if r.bid else None,
            ask=float(r.ask) if r.ask else None,
            spread=spread,
            source=source_name,
            timestamp=r.rate_timestamp
        ))

    return result


@router.get(
    "/statistics/{quote}",
    response_model=RateStatistics,
    summary="Get rate statistics",
    description="Returns statistical summary for a currency pair over a period"
)
@cache(expire=300)  # Cache 5 min
async def get_rate_statistics(
    quote: str,
    base: str = Query(default="BRL", pattern="^[A-Z]{3}$"),
    days: int = Query(default=30, ge=1, le=365),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca estatísticas de um par"""
    stats = await repo.get_statistics(base, quote, days)

    if not stats or stats.get("count", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data for {base}/{quote} in the last {days} days"
        )

    return RateStatistics(**stats)


@router.get(
    "/statistics/influx/{quote}",
    response_model=RateStatistics,
    summary="Get rate statistics from InfluxDB",
    description="Returns statistical summary using InfluxDB aggregation"
)
async def get_rate_statistics_influx(
    quote: str,
    base: str = Query(default="BRL", pattern="^[A-Z]{3}$"),
    days: int = Query(default=30, ge=1, le=365),
    influxdb: InfluxDBClient = Depends(get_influxdb)
):
    """Busca estatísticas via InfluxDB (mais rápido para grandes volumes)"""
    start = datetime.utcnow() - timedelta(days=days)
    stats = await influxdb.query_statistics(base, quote, start)

    if not stats or stats.get("count", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data for {base}/{quote} in the last {days} days"
        )

    return RateStatistics(**stats)


# Import timedelta for statistics endpoint
from datetime import timedelta