import httpx
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime
from .base import BaseSource, ExchangeRate, CollectionResult, RateType
from currency_tracker.config.settings import get_settings

class AwesomeAPISource(BaseSource):

    def __init__(self, api_key: str='', timeout: float=30.0):
        super().__init__(name='awesomeapi', base_url='https://economia.awesomeapi.com.br', api_key=api_key, timeout=timeout, rate_limit=10)
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        start_time = datetime.utcnow()
        errors = []
        rates = []
        try:
            pairs = []
            for quote in quotes:
                if base == 'BRL':
                    pairs.append(f'{quote}-{base}')
                else:
                    pairs.append(f'{base}-{quote}')
            pairs_str = ','.join(pairs)
            url = f'{self.base_url}/json/last/{pairs_str}'
            self._rate_limit_wait()
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            rates = self.parse_response(data, base, quotes)
        except httpx.HTTPStatusError as e:
            errors.append(f'HTTP {e.response.status_code}: {e.response.text}')
        except httpx.RequestError as e:
            errors.append(f'Request error: {str(e)}')
        except Exception as e:
            errors.append(f'Unexpected error: {str(e)}')
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        return CollectionResult(success=len(errors) == 0, rates=rates, errors=errors, source=self.name, duration_ms=duration_ms, timestamp=datetime.utcnow())

    def parse_response(self, response: Dict[str, Any], base: str, quotes: List[str]) -> List[ExchangeRate]:
        rates = []
        for quote in quotes:
            if base == 'BRL':
                key = f'{quote}{base}'
            else:
                key = f'{base}{quote}'
            if key not in response:
                inv_key = f'{quote}{base}' if base != 'BRL' else f'{base}{quote}'
                if inv_key in response:
                    key = inv_key
                else:
                    continue
            data = response[key]
            try:
                bid = Decimal(str(data.get('bid', 0)))
                ask = Decimal(str(data.get('ask', 0)))
                rate = bid if bid > 0 else ask
                if rate <= 0:
                    continue
                if base != 'BRL':
                    rate = Decimal('1') / rate
                    bid, ask = (Decimal('1') / ask, Decimal('1') / bid) if ask and bid else (None, None)
                exchange_rate = self._create_rate(base=base, quote=quote, rate=float(rate), bid=float(bid) if bid else None, ask=float(ask) if ask else None, rate_type=RateType.COMMERCIAL, raw_data=data)
                rates.append(exchange_rate)
            except (ValueError, KeyError, TypeError) as e:
                continue
        return rates

    async def fetch_historical(self, base: str, quote: str, days: int=30) -> List[ExchangeRate]:
        rates = []
        try:
            if base == 'BRL':
                pair = f'{quote}-{base}'
            else:
                pair = f'{base}-{quote}'
            url = f'{self.base_url}/json/daily/{pair}/{days}'
            self._rate_limit_wait()
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            for item in data:
                try:
                    bid = Decimal(str(item.get('bid', 0)))
                    ask = Decimal(str(item.get('ask', 0)))
                    rate = bid if bid > 0 else ask
                    if rate <= 0:
                        continue
                    if base != 'BRL':
                        rate = Decimal('1') / rate
                        bid, ask = (Decimal('1') / ask, Decimal('1') / bid) if ask and bid else (None, None)
                    timestamp = datetime.strptime(item['timestamp'], '%Y-%m-%d %H:%M:%S')
                    exchange_rate = self._create_rate(base=base, quote=quote, rate=float(rate), bid=float(bid) if bid else None, ask=float(ask) if ask else None, rate_type=RateType.COMMERCIAL, raw_data=item)
                    exchange_rate.timestamp = timestamp
                    rates.append(exchange_rate)
                except (ValueError, KeyError, TypeError):
                    continue
        except Exception:
            pass
        return rates

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
