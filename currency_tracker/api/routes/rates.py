from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from currency_tracker.api.schemas import ExchangeRateLatest, RateHistoryQuery, RateStatistics
from currency_tracker.storage.repository import RateRepository
from currency_tracker.config.settings import get_settings
from currency_tracker.api.dependencies import get_rate_repo
router = APIRouter(prefix='/rates', tags=['Exchange Rates'])

def _to_latest(r, base, quote_fallback, source_fallback=None):
    spread = float(r.spread) if r.spread else None
    if r.bid and r.ask and (r.bid > 0):
        spread = float((r.ask - r.bid) / r.bid * 100)
    return ExchangeRateLatest(base=r.base_currency_rel.code if r.base_currency_rel else base, quote=r.quote_currency_rel.code if r.quote_currency_rel else quote_fallback, rate=float(r.rate), bid=float(r.bid) if r.bid else None, ask=float(r.ask) if r.ask else None, spread=spread, source=r.source_rel.name if r.source_rel else source_fallback or 'unknown', timestamp=r.rate_timestamp)

@router.get('/latest', response_model=List[ExchangeRateLatest], summary='Get latest exchange rates')
async def get_latest_rates(base: str=Query(default='BRL', pattern='^[A-Z]{3}$'), sources: Optional[List[str]]=Query(default=None), repo: RateRepository=Depends(get_rate_repo)):
    rates = await repo.get_latest_rates_all_pairs(base, sources)
    return [_to_latest(r, base, 'UNKNOWN') for r in rates]

@router.get('/latest/{quote}', response_model=ExchangeRateLatest, summary='Get latest rate for specific pair')
async def get_latest_rate(quote: str, base: str=Query(default='BRL', pattern='^[A-Z]{3}$'), source: Optional[str]=Query(default=None), repo: RateRepository=Depends(get_rate_repo)):
    rate = await repo.get_latest_rate(base, quote, source)
    if not rate:
        raise HTTPException(status_code=404, detail=f'No rate found for {base}/{quote}')
    return _to_latest(rate, base, quote)

@router.post('/history', response_model=List[ExchangeRateLatest], summary='Get historical rates')
async def get_rates_history(query: RateHistoryQuery, repo: RateRepository=Depends(get_rate_repo)):
    rates = await repo.get_rates_history(base=query.base, quote=query.quote, start_date=query.start_date, end_date=query.end_date, source=query.source, limit=query.limit)
    return [_to_latest(r, query.base, query.quote) for r in rates]

@router.get('/statistics/{quote}', response_model=RateStatistics, summary='Get rate statistics')
async def get_rate_statistics(quote: str, base: str=Query(default='BRL', pattern='^[A-Z]{3}$'), days: int=Query(default=30, ge=1, le=365), repo: RateRepository=Depends(get_rate_repo)):
    stats = await repo.get_statistics(base, quote, days)
    if not stats or stats.get('count', 0) == 0:
        raise HTTPException(status_code=404, detail=f'No data for {base}/{quote} in the last {days} days')
    return RateStatistics(**stats)

@router.post('/collect', summary='Trigger live collection')
async def collect_now(base: str=Query(default='BRL', pattern='^[A-Z]{3}$'), repo: RateRepository=Depends(get_rate_repo)):
    settings = get_settings()
    quotes = settings.tracked_currency_list or ['USD', 'EUR', 'GBP', 'JPY']
    from currency_tracker.collector.sources.awesomeapi import AwesomeAPISource
    source = AwesomeAPISource()
    try:
        result = await source.fetch_rates(base, quotes)
        saved = 0
        for r in result.rates:
            await repo.save_rate(r)
            saved += 1
        return {'collected': saved, 'errors': result.errors, 'source': 'awesomeapi', 'at': datetime.utcnow().isoformat()}
    finally:
        await source.close()
