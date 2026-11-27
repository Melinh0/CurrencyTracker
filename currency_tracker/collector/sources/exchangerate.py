# ============================================
# CurrencyTracker - ExchangeRate-API Source
# ============================================
# Documentação: https://www.exchangerate-api.com/docs/overview

import httpx
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime

from .base import BaseSource, ExchangeRate, CollectionResult, RateType
from currency_tracker.config.settings import get_settings


class ExchangeRateAPISource(BaseSource):
    """Fonte de dados da ExchangeRate-API (160+ moedas)"""

    def __init__(self, api_key: str = "", timeout: float = 30.0):
        # Se não tem chave, usa versão gratuita (limitada)
        base_url = "https://v6.exchangerate-api.com/v6"
        if api_key:
            base_url = f"{base_url}/{api_key}"
        else:
            # Versão gratuita sem chave (apenas USD como base)
            base_url = "https://open.er-api.com/v6"

        super().__init__(
            name="exchangerate",
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            rate_limit=5  # 5 req/s
        )
        self.client = httpx.AsyncClient(timeout=timeout)
        self._has_key = bool(api_key)

    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        """Busca taxas da ExchangeRate-API"""
        start_time = datetime.utcnow()
        errors = []
        rates = []

        try:
            # Versão gratuita só suporta USD como base
            if not self._has_key and base != "USD":
                errors.append("Free tier only supports USD as base currency")
                return CollectionResult(
                    success=False,
                    rates=[],
                    errors=errors,
                    source=self.name,
                    duration_ms=0,
                    timestamp=datetime.utcnow()
                )

            # Endpoint: /latest/{BASE}
            url = f"{self.base_url}/latest/{base}"

            self._rate_limit_wait()
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("result") == "error":
                errors.append(data.get("error-type", "Unknown error"))
            else:
                rates = self.parse_response(data, base, quotes)

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

    def parse_response(self, response: Dict[str, Any], base: str, quotes: List[str]) -> List[ExchangeRate]:
        """Converte resposta da ExchangeRate-API em ExchangeRate"""
        rates = []

        conversion_rates = response.get("conversion_rates", {})
        time_last_update = response.get("time_last_update_unix")

        for quote in quotes:
            if quote not in conversion_rates:
                continue

            try:
                rate = Decimal(str(conversion_rates[quote]))

                if rate <= 0:
                    continue

                # Se base não é USD e não temos chave, a API retorna base=USD
                # Precisamos converter: 1 BASE = X QUOTE
                # API retorna: 1 USD = X QUOTE
                # Se base=BRL: 1 BRL = (1 USD / X BRL) * X QUOTE = X QUOTE / X BRL
                if not self._has_key and base != "USD":
                    base_rate = Decimal(str(conversion_rates.get(base, 0)))
                    if base_rate > 0:
                        rate = rate / base_rate

                timestamp = datetime.utcnow()
                if time_last_update:
                    timestamp = datetime.fromtimestamp(time_last_update)

                exchange_rate = self._create_rate(
                    base=base,
                    quote=quote,
                    rate=float(rate),
                    rate_type=RateType.OFFICIAL,
                    raw_data={
                        "source_rate": float(conversion_rates[quote]),
                        "time_last_update": time_last_update
                    }
                )
                exchange_rate.timestamp = timestamp
                rates.append(exchange_rate)

            except (ValueError, KeyError, TypeError):
                continue

        return rates

    async def fetch_historical(self, base: str, quote: str, date: str) -> List[ExchangeRate]:
        """Busca taxa histórica para uma data específica (YYYY-MM-DD)"""
        rates = []

        if not self._has_key:
            return rates  # Histórico só na versão paga

        try:
            url = f"{self.base_url}/history/{base}/{date}"

            self._rate_limit_wait()
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("result") == "success":
                conversion_rates = data.get("conversion_rates", {})
                if quote in conversion_rates:
                    rate = Decimal(str(conversion_rates[quote]))
                    if rate > 0:
                        exchange_rate = self._create_rate(
                            base=base,
                            quote=quote,
                            rate=float(rate),
                            rate_type=RateType.OFFICIAL,
                            raw_data=data
                        )
                        exchange_rate.timestamp = datetime.strptime(date, "%Y-%m-%d")
                        rates.append(exchange_rate)

        except Exception:
            pass

        return rates

    async def get_supported_currencies(self) -> Dict[str, str]:
        """Retorna moedas suportadas (código -> nome)"""
        try:
            url = f"{self.base_url}/codes"
            self._rate_limit_wait()
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("result") == "success":
                return {code: name for code, name in data.get("supported_codes", [])}
        except Exception:
            pass
        return {}

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()