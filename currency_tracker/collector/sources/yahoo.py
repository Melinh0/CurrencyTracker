import yfinance as yf
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from .base import BaseSource, ExchangeRate, CollectionResult, RateType

class YahooFinanceSource(BaseSource):
    CURRENCY_MAP = {'USD': 'USD', 'EUR': 'EUR', 'GBP': 'GBP', 'JPY': 'JPY', 'CHF': 'CHF', 'CAD': 'CAD', 'AUD': 'AUD', 'CNY': 'CNY', 'INR': 'INR', 'ZAR': 'ZAR', 'MXN': 'MXN', 'ARS': 'ARS', 'CLP': 'CLP', 'COP': 'COP', 'RUB': 'RUB', 'TRY': 'TRY'}

    def __init__(self, timeout: float=30.0):
        super().__init__(name='yahoo', base_url='https://query1.finance.yahoo.com', timeout=timeout, rate_limit=20)

    def _get_symbol(self, base: str, quote: str) -> str:
        if base == 'BRL':
            return f'{quote}{base}=X'
        return f'{base}{quote}=X'

    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        start_time = datetime.utcnow()
        errors = []
        rates = []
        try:
            symbols = [self._get_symbol(base, q) for q in quotes]
            tickers = yf.Tickers(' '.join(symbols))
            for quote, symbol in zip(quotes, symbols):
                try:
                    ticker = tickers.tickers.get(symbol)
                    if not ticker:
                        continue
                    info = ticker.info
                    if not info:
                        hist = ticker.history(period='1d', interval='1m')
                        if hist.empty:
                            continue
                        rate = Decimal(str(hist['Close'].iloc[-1]))
                        timestamp = hist.index[-1].to_pydatetime()
                    else:
                        rate = Decimal(str(info.get('regularMarketPrice', 0)))
                        timestamp = datetime.utcnow()
                        bid = info.get('bid')
                        ask = info.get('ask')
                    if rate <= 0:
                        continue
                    if base == 'BRL':
                        rate = Decimal('1') / rate
                        if bid and ask:
                            bid, ask = (Decimal('1') / Decimal(str(ask)), Decimal('1') / Decimal(str(bid)))
                    exchange_rate = self._create_rate(base=base, quote=quote, rate=float(rate), bid=float(bid) if bid else None, ask=float(ask) if ask else None, rate_type=RateType.COMMERCIAL, raw_data={'symbol': symbol, 'info': info})
                    exchange_rate.timestamp = timestamp
                    rates.append(exchange_rate)
                except Exception as e:
                    errors.append(f'{quote}: {str(e)}')
                    continue
        except Exception as e:
            errors.append(f'Unexpected error: {str(e)}')
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        return CollectionResult(success=len(errors) == 0, rates=rates, errors=errors, source=self.name, duration_ms=duration_ms, timestamp=datetime.utcnow())

    async def fetch_historical(self, base: str, quote: str, period: str='1mo', interval: str='1d') -> List[ExchangeRate]:
        rates = []
        try:
            symbol = self._get_symbol(base, quote)
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                return rates
            for timestamp, row in hist.iterrows():
                try:
                    rate = Decimal(str(row['Close']))
                    if rate <= 0:
                        continue
                    if base == 'BRL':
                        rate = Decimal('1') / rate
                    exchange_rate = self._create_rate(base=base, quote=quote, rate=float(rate), rate_type=RateType.COMMERCIAL, raw_data={'open': float(row['Open']), 'high': float(row['High']), 'low': float(row['Low']), 'close': float(row['Close']), 'volume': int(row['Volume']) if row['Volume'] > 0 else 0})
                    exchange_rate.timestamp = timestamp.to_pydatetime()
                    rates.append(exchange_rate)
                except (ValueError, KeyError, TypeError):
                    continue
        except Exception:
            pass
        return rates

    async def fetch_intraday(self, base: str, quote: str, interval: str='1m', period: str='1d') -> List[ExchangeRate]:
        return await self.fetch_historical(base, quote, period=period, interval=interval)

    def get_currency_info(self, base: str, quote: str) -> Dict[str, Any]:
        symbol = self._get_symbol(base, quote)
        ticker = yf.Ticker(symbol)
        return ticker.info

    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
