# ============================================
# CurrencyTracker - Alpha Vantage Source
# ============================================
# Documentação: https://www.alphavantage.co/documentation/
# Requer API key gratuita: https://www.alphavantage.co/support/#api-key

import httpx
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from enum import Enum

from .base import BaseSource, ExchangeRate, CollectionResult, RateType
from currency_tracker.config.settings import get_settings


class AVFunction(str, Enum):
    """Funções da API Alpha Vantage"""
    CURRENCY_EXCHANGE_RATE = "CURRENCY_EXCHANGE_RATE"
    FX_DAILY = "FX_DAILY"
    FX_WEEKLY = "FX_WEEKLY"
    FX_MONTHLY = "FX_MONTHLY"
    FX_INTRADAY = "FX_INTRADAY"


class AlphaVantageSource(BaseSource):
    """Fonte de dados da Alpha Vantage"""

    def __init__(self, api_key: str = "", timeout: float = 30.0):
        super().__init__(
            name="alphavantage",
            base_url="https://www.alphavantage.co/query",
            api_key=api_key,
            timeout=timeout,
            rate_limit=5  # 5 req/min para free tier
        )
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        """Busca taxas em tempo real (CURRENCY_EXCHANGE_RATE)"""
        start_time = datetime.utcnow()
        errors = []
        rates = []

        if not self.api_key:
            errors.append("Alpha Vantage API key required")
            return CollectionResult(
                success=False,
                rates=[],
                errors=errors,
                source=self.name,
                duration_ms=0,
                timestamp=datetime.utcnow()
            )

        try:
            # Alpha Vantage faz uma requisição por par
            for quote in quotes:
                self._rate_limit_wait()

                params = {
                    "function": AVFunction.CURRENCY_EXCHANGE_RATE,
                    "from_currency": base,
                    "to_currency": quote,
                    "apikey": self.api_key
                }

                response = await self.client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

                # Verifica erro da API
                if "Error Message" in data:
                    errors.append(f"{base}/{quote}: {data['Error Message']}")
                    continue
                if "Note" in data:
                    errors.append(f"Rate limit: {data['Note']}")
                    break

                parsed = self._parse_realtime_response(data, base, quote)
                if parsed:
                    rates.append(parsed)

        except httpx.HTTPStatusError as e:
            errors.append(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            errors.append(f"Request error: {str(e)}")
        except Exception as e:
            errors.append(f"Unexpected error: {str(e)}")

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return CollectionResult(
            success=len(errors) == 0,
            rates=rates,
            errors=errors,
            source=self.name,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow()
        )

    def _parse_realtime_response(self, data: Dict, base: str, quote: str) -> Optional[ExchangeRate]:
        """Parse da resposta CURRENCY_EXCHANGE_RATE"""
        try:
            rate_data = data.get("Realtime Currency Exchange Rate", {})
            if not rate_data:
                return None

            rate = Decimal(str(rate_data.get("5. Exchange Rate", 0)))
            bid = Decimal(str(rate_data.get("8. Bid Price", 0))) or None
            ask = Decimal(str(rate_data.get("9. Ask Price", 0))) or None

            if rate <= 0:
                return None

            # Timestamp: "6. Last Refreshed" = "2024-01-15 12:00:00"
            timestamp_str = rate_data.get("6. Last Refreshed", "")
            timestamp = datetime.utcnow()
            if timestamp_str:
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            return self._create_rate(
                base=base,
                quote=quote,
                rate=float(rate),
                bid=float(bid) if bid else None,
                ask=float(ask) if ask else None,
                rate_type=RateType.COMMERCIAL,
                raw_data=rate_data
            )
        except (ValueError, KeyError, TypeError):
            return None

    def parse_response(self, response: Dict[str, Any], base: str, quotes: List[str]) -> List[ExchangeRate]:
        """Método abstrato - não usado diretamente (usa fetch_rates)"""
        return []

    async def fetch_historical_daily(
        self,
        base: str,
        quote: str,
        outputsize: str = "compact"  # "compact" (100) ou "full" (tudo)
    ) -> List[ExchangeRate]:
        """Busca dados históricos diários (FX_DAILY)"""
        rates = []

        if not self.api_key:
            return rates

        try:
            self._rate_limit_wait()

            params = {
                "function": AVFunction.FX_DAILY,
                "from_symbol": base,
                "to_symbol": quote,
                "outputsize": outputsize,
                "apikey": self.api_key
            }

            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if "Error Message" in data:
                return rates

            time_series = data.get("Time Series FX (Daily)", {})
            for date_str, values in time_series.items():
                try:
                    # Values: "1. open", "2. high", "3. low", "4. close"
                    close_rate = Decimal(str(values.get("4. close", 0)))
                    if close_rate <= 0:
                        continue

                    timestamp = datetime.strptime(date_str, "%Y-%m-%d")

                    exchange_rate = self._create_rate(
                        base=base,
                        quote=quote,
                        rate=float(close_rate),
                        rate_type=RateType.OFFICIAL,
                        raw_data={"date": date_str, **values}
                    )
                    exchange_rate.timestamp = timestamp
                    rates.append(exchange_rate)

                except (ValueError, KeyError, TypeError):
                    continue

        except Exception:
            pass

        return rates

    async def fetch_intraday(
        self,
        base: str,
        quote: str,
        interval: str = "60min",  # 1min, 5min, 15min, 30min, 60min
        outputsize: str = "compact"
    ) -> List[ExchangeRate]:
        """Busca dados intraday (FX_INTRADAY)"""
        rates = []

        if not self.api_key:
            return rates

        try:
            self._rate_limit_wait()

            params = {
                "function": AVFunction.FX_INTRADAY,
                "from_symbol": base,
                "to_symbol": quote,
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self.api_key
            }

            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            time_series_key = f"Time Series FX ({interval})"
            time_series = data.get(time_series_key, {})

            for timestamp_str, values in time_series.items():
                try:
                    close_rate = Decimal(str(values.get("4. close", 0)))
                    if close_rate <= 0:
                        continue

                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                    exchange_rate = self._create_rate(
                        base=base,
                        quote=quote,
                        rate=float(close_rate),
                        rate_type=RateType.COMMERCIAL,
                        raw_data={"timestamp": timestamp_str, **values}
                    )
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