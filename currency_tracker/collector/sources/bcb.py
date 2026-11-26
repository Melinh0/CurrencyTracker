import httpx
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from .base import BaseSource, ExchangeRate, CollectionResult, RateType
from currency_tracker.config.settings import get_settings

class BCBSource(BaseSource):
    SGS_CODES = {'USD': 1, 'USD_SELL': 21619, 'EUR': 21620, 'EUR_SELL': 21621, 'GBP': 21622, 'GBP_SELL': 21623, 'JPY': 21624, 'JPY_SELL': 21625, 'CHF': 21626, 'CHF_SELL': 21627, 'CAD': 21628, 'CAD_SELL': 21629, 'AUD': 21630, 'AUD_SELL': 21631, 'ARS': 21632, 'ARS_SELL': 21633}

    def __init__(self, timeout: float=30.0):
        super().__init__(name='bcb', base_url='https://api.bcb.gov.br/dados/serie/bcdata.sgs', timeout=timeout, rate_limit=10)
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        start_time = datetime.utcnow()
        errors = []
        rates = []
        if base != 'BRL':
            errors.append('BCB only provides rates against BRL')
            return CollectionResult(success=False, rates=[], errors=errors, source=self.name, duration_ms=0, timestamp=datetime.utcnow())
        try:
            end_date = datetime.utcnow().strftime('%d/%m/%Y')
            start_date = (datetime.utcnow() - timedelta(days=5)).strftime('%d/%m/%Y')
            for quote in quotes:
                buy_code = self.SGS_CODES.get(quote)
                sell_code = self.SGS_CODES.get(f'{quote}_SELL')
                if not buy_code:
                    continue
                buy_rate = await self._fetch_series(buy_code, start_date, end_date)
                sell_rate = await self._fetch_series(sell_code, start_date, end_date) if sell_code else None
                if buy_rate:
                    rate = Decimal(str(buy_rate['valor']))
                    bid = Decimal(str(buy_rate['valor']))
                    ask = Decimal(str(sell_rate['valor'])) if sell_rate else None
                    timestamp = datetime.strptime(buy_rate['data'], '%d/%m/%Y')
                    exchange_rate = self._create_rate(base='BRL', quote=quote, rate=float(rate), bid=float(bid), ask=float(ask) if ask else None, rate_type=RateType.OFFICIAL, raw_data={'buy': buy_rate, 'sell': sell_rate})
                    exchange_rate.timestamp = timestamp
                    rates.append(exchange_rate)
        except Exception as e:
            errors.append(f'Unexpected error: {str(e)}')
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        return CollectionResult(success=len(errors) == 0, rates=rates, errors=errors, source=self.name, duration_ms=duration_ms, timestamp=datetime.utcnow())

    async def _fetch_series(self, code: int, start_date: str, end_date: str) -> Optional[Dict]:
        try:
            url = f'{self.base_url}/{code}/dados'
            params = {'formato': 'json', 'dataInicial': start_date, 'dataFinal': end_date}
            self._rate_limit_wait()
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                return data[-1]
        except Exception:
            pass
        return None

    def parse_response(self, response: Dict[str, Any], base: str, quotes: List[str]) -> List[ExchangeRate]:
        return []

    async def fetch_historical(self, quote: str, start_date: str, end_date: str) -> List[ExchangeRate]:
        rates = []
        buy_code = self.SGS_CODES.get(quote)
        sell_code = self.SGS_CODES.get(f'{quote}_SELL')
        if not buy_code:
            return rates
        try:
            buy_data = await self._fetch_series_range(buy_code, start_date, end_date)
            sell_data = await self._fetch_series_range(sell_code, start_date, end_date) if sell_code else {}
            sell_by_date = {item['data']: item for item in sell_data}
            for buy_item in buy_data:
                try:
                    date_str = buy_item['data']
                    buy_val = Decimal(str(buy_item['valor']))
                    sell_val = Decimal(str(sell_by_date[date_str]['valor'])) if date_str in sell_by_date else None
                    if buy_val <= 0:
                        continue
                    timestamp = datetime.strptime(date_str, '%d/%m/%Y')
                    exchange_rate = self._create_rate(base='BRL', quote=quote, rate=float(buy_val), bid=float(buy_val), ask=float(sell_val) if sell_val else None, rate_type=RateType.OFFICIAL, raw_data={'buy': buy_item, 'sell': sell_by_date.get(date_str)})
                    exchange_rate.timestamp = timestamp
                    rates.append(exchange_rate)
                except (ValueError, KeyError, TypeError):
                    continue
        except Exception:
            pass
        return rates

    async def _fetch_series_range(self, code: int, start_date: str, end_date: str) -> List[Dict]:
        try:
            url = f'{self.base_url}/{code}/dados'
            params = {'formato': 'json', 'dataInicial': start_date, 'dataFinal': end_date}
            self._rate_limit_wait()
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception:
            return []

    async def get_latest_date(self) -> Optional[datetime]:
        try:
            data = await self._fetch_series(self.SGS_CODES['USD'], (datetime.utcnow() - timedelta(days=10)).strftime('%d/%m/%Y'), datetime.utcnow().strftime('%d/%m/%Y'))
            if data:
                return datetime.strptime(data['data'], '%d/%m/%Y')
        except Exception:
            pass
        return None

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
