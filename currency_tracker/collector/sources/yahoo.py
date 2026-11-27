# ============================================
# CurrencyTracker - Yahoo Finance Source
# ============================================
# Usa biblioteca yfinance para buscar dados do Yahoo Finance
# Suporta: moedas, criptomoedas, ações, índices

import yfinance as yf
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd

from .base import BaseSource, ExchangeRate, CollectionResult, RateType
from currency_tracker.config.settings import get_settings


class YahooFinanceSource(BaseSource):
    """Fonte de dados do Yahoo Finance via yfinance"""

    # Mapeamento de moedas para símbolos do Yahoo Finance
    # Formato: MOEDABASE=X (ex: USDBRL=X para USD/BRL)
    # Para base BRL: BRLUSD=X (inverso)
    CURRENCY_MAP = {
        "USD": "USD",
        "EUR": "EUR",
        "GBP": "GBP",
        "JPY": "JPY",
        "CHF": "CHF",
        "CAD": "CAD",
        "AUD": "AUD",
        "CNY": "CNY",
        "INR": "INR",
        "ZAR": "ZAR",
        "MXN": "MXN",
        "ARS": "ARS",
        "CLP": "CLP",
        "COP": "COP",
        "RUB": "RUB",
        "TRY": "TRY",
    }

    def __init__(self, timeout: float = 30.0):
        super().__init__(
            name="yahoo",
            base_url="https://query1.finance.yahoo.com",
            timeout=timeout,
            rate_limit=20
        )
        # yfinance não precisa de client HTTP próprio

    def _get_symbol(self, base: str, quote: str) -> str:
        """Gera símbolo do Yahoo Finance"""
        # Yahoo usa formato: BASEQUOTE=X
        # Ex: USDBRL=X (1 USD = X BRL)
        if base == "BRL":
            # Para base BRL, precisamos do inverso: BRLUSD=X
            # Mas Yahoo não tem todos pares com BRL base
            # Usamos USDBRL=X e invertemos
            return f"{quote}{base}=X"
        return f"{base}{quote}=X"

    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        """Busca taxas atuais do Yahoo Finance"""
        start_time = datetime.utcnow()
        errors = []
        rates = []

        try:
            symbols = [self._get_symbol(base, q) for q in quotes]
            # yfinance pode buscar múltiplos símbolos de uma vez
            tickers = yf.Tickers(" ".join(symbols))

            for quote, symbol in zip(quotes, symbols):
                try:
                    ticker = tickers.tickers.get(symbol)
                    if not ticker:
                        continue

                    # Pega info mais recente
                    info = ticker.info
                    if not info:
                        # Tenta history de 1 dia
                        hist = ticker.history(period="1d", interval="1m")
                        if hist.empty:
                            continue
                        rate = Decimal(str(hist["Close"].iloc[-1]))
                        timestamp = hist.index[-1].to_pydatetime()
                    else:
                        rate = Decimal(str(info.get("regularMarketPrice", 0)))
                        timestamp = datetime.utcnow()
                        # Tenta pegar bid/ask
                        bid = info.get("bid")
                        ask = info.get("ask")

                    if rate <= 0:
                        continue

                    # Yahoo retorna: 1 BASE = X QUOTE
                    # Se base=BRL e símbolo=USDBRL=X, rate = 1 USD = X BRL
                    # Precisamos: 1 BRL = 1/X USD
                    if base == "BRL":
                        rate = Decimal("1") / rate
                        if bid and ask:
                            bid, ask = Decimal("1") / Decimal(str(ask)), Decimal("1") / Decimal(str(bid))

                    exchange_rate = self._create_rate(
                        base=base,
                        quote=quote,
                        rate=float(rate),
                        bid=float(bid) if bid else None,
                        ask=float(ask) if ask else None,
                        rate_type=RateType.COMMERCIAL,
                        raw_data={"symbol": symbol, "info": info}
                    )
                    exchange_rate.timestamp = timestamp
                    rates.append(exchange_rate)

                except Exception as e:
                    errors.append(f"{quote}: {str(e)}")
                    continue

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
        """Método abstrato - não usado diretamente"""
        return []

    async def fetch_historical(
        self,
        base: str,
        quote: str,
        period: str = "1mo",  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: str = "1d"  # 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    ) -> List[ExchangeRate]:
        """Busca dados históricos do Yahoo Finance"""
        rates = []

        try:
            symbol = self._get_symbol(base, quote)
            ticker = yf.Ticker(symbol)

            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                return rates

            for timestamp, row in hist.iterrows():
                try:
                    rate = Decimal(str(row["Close"]))
                    if rate <= 0:
                        continue

                    if base == "BRL":
                        rate = Decimal("1") / rate

                    exchange_rate = self._create_rate(
                        base=base,
                        quote=quote,
                        rate=float(rate),
                        rate_type=RateType.COMMERCIAL,
                        raw_data={
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "volume": int(row["Volume"]) if row["Volume"] > 0 else 0
                        }
                    )
                    exchange_rate.timestamp = timestamp.to_pydatetime()
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
        interval: str = "1m",  # 1m, 2m, 5m, 15m, 30m, 60m, 90m
        period: str = "1d"
    ) -> List[ExchangeRate]:
        """Busca dados intraday (limitado a 7 dias para intervalos < 1h)"""
        return await self.fetch_historical(base, quote, period=period, interval=interval)

    def get_currency_info(self, base: str, quote: str) -> Dict[str, Any]:
        """Retorna informações completas do par"""
        symbol = self._get_symbol(base, quote)
        ticker = yf.Ticker(symbol)
        return ticker.info

    async def close(self):
        pass  # yfinance não precisa fechar conexão

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass