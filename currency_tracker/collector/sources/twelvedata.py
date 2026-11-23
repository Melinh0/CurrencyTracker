# ============================================
# CurrencyTracker - Twelve Data Source
# ============================================
# WebSocket para dados em tempo real
# Documentação: https://twelvedata.com/docs
# Requer API key: https://twelvedata.com/apikey

import json
import asyncio
import websockets
import httpx
from typing import List, Dict, Any, Optional, Callable, Set
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass, field

from .base import BaseSource, ExchangeRate, CollectionResult, RateType
from currency_tracker.config.settings import get_settings


@dataclass
class WSMessage:
    """Mensagem recebida do WebSocket"""
    symbol: str
    price: Decimal
    timestamp: datetime
    volume: Optional[Decimal] = None
    raw: Dict = field(default_factory=dict)


class TwelveDataSource(BaseSource):
    """Fonte de dados da Twelve Data (REST + WebSocket)"""

    def __init__(self, api_key: str = "", timeout: float = 30.0):
        super().__init__(
            name="twelvedata",
            base_url="https://api.twelvedata.com",
            api_key=api_key,
            timeout=timeout,
            rate_limit=8  # 8 req/s
        )
        self.ws_url = "wss://ws.twelvedata.com/v1/quotes/price"
        self.client = httpx.AsyncClient(timeout=timeout)
        self._ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._subscriptions: Set[str] = set()
        self._callbacks: List[Callable[[WSMessage], None]] = []
        self._running = False

    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        """Busca taxas via REST API (price endpoint)"""
        start_time = datetime.utcnow()
        errors = []
        rates = []

        if not self.api_key:
            errors.append("Twelve Data API key required")
            return CollectionResult(
                success=False,
                rates=[],
                errors=errors,
                source=self.name,
                duration_ms=0,
                timestamp=datetime.utcnow()
            )

        try:
            # Twelve Data usa formato: BASE/QUOTE (ex: USD/BRL)
            symbols = []
            for quote in quotes:
                if base == "BRL":
                    symbols.append(f"{quote}/{base}")
                else:
                    symbols.append(f"{base}/{quote}")

            symbols_str = ",".join(symbols)
            url = f"{self.base_url}/price"

            self._rate_limit_wait()
            response = await self.client.get(url, params={
                "symbol": symbols_str,
                "apikey": self.api_key
            })
            response.raise_for_status()
            data = response.json()

            # Resposta: {"USD/BRL": {"price": "5.20", "currency_base": "USD", "currency_quote": "BRL"}, ...}
            for quote, symbol in zip(quotes, symbols):
                if symbol in data:
                    try:
                        price_data = data[symbol]
                        price = Decimal(str(price_data.get("price", 0)))

                        if price <= 0:
                            continue

                        # Twelve Data retorna: 1 BASE = X QUOTE
                        if base == "BRL":
                            price = Decimal("1") / price

                        exchange_rate = self._create_rate(
                            base=base,
                            quote=quote,
                            rate=float(price),
                            rate_type=RateType.COMMERCIAL,
                            raw_data=price_data
                        )
                        rates.append(exchange_rate)

                    except (ValueError, KeyError, TypeError):
                        continue

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
        """Método abstrato - não usado diretamente"""
        return []

    # ============================================
    # WebSocket Methods
    # ============================================

    async def connect_websocket(self) -> bool:
        """Conecta ao WebSocket da Twelve Data"""
        if not self.api_key:
            return False

        try:
            self._ws_connection = await websockets.connect(
                f"{self.ws_url}?apikey={self.api_key}",
                ping_interval=20,
                ping_timeout=10
            )
            self._running = True
            self._ws_task = asyncio.create_task(self._ws_listener())
            return True
        except Exception:
            return False

    async def disconnect_websocket(self):
        """Desconecta do WebSocket"""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None

    async def _ws_listener(self):
        """Loop de escuta do WebSocket"""
        try:
            async for message in self._ws_connection:
                if not self._running:
                    break
                await self._handle_ws_message(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            pass

    async def _handle_ws_message(self, message: str):
        """Processa mensagem do WebSocket"""
        try:
            data = json.loads(message)

            # Formato: {"event": "price", "symbol": "USD/BRL", "price": "5.20", "timestamp": 1705320000}
            if data.get("event") == "price":
                symbol = data.get("symbol", "")
                price_str = data.get("price", "")
                timestamp_ms = data.get("timestamp", 0)

                if symbol and price_str:
                    price = Decimal(str(price_str))
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else datetime.utcnow()

                    # Parse symbol: "USD/BRL" -> base="USD", quote="BRL"
                    parts = symbol.split("/")
                    if len(parts) == 2:
                        base, quote = parts
                        # Normaliza para base=BRL se necessário
                        if base == "BRL":
                            price = Decimal("1") / price
                            base, quote = quote, base

                        msg = WSMessage(
                            symbol=symbol,
                            price=price,
                            timestamp=timestamp,
                            raw=data
                        )
                        # Notifica callbacks
                        for callback in self._callbacks:
                            try:
                                callback(msg)
                            except Exception:
                                pass

        except Exception:
            pass

    def subscribe(self, symbols: List[str]):
        """Inscreve em símbolos no WebSocket"""
        if not self._ws_connection:
            return

        # Formato: {"action": "subscribe", "params": {"symbols": "USD/BRL,EUR/BRL"}}
        symbols_str = ",".join(symbols)
        message = json.dumps({
            "action": "subscribe",
            "params": {"symbols": symbols_str}
        })

        asyncio.create_task(self._ws_connection.send(message))
        self._subscriptions.update(symbols)

    def unsubscribe(self, symbols: List[str]):
        """Remove inscrição de símbolos"""
        if not self._ws_connection:
            return

        symbols_str = ",".join(symbols)
        message = json.dumps({
            "action": "unsubscribe",
            "params": {"symbols": symbols_str}
        })

        asyncio.create_task(self._ws_connection.send(message))
        self._subscriptions.difference_update(symbols)

    def on_price_update(self, callback: Callable[[WSMessage], None]):
        """Registra callback para atualizações de preço"""
        self._callbacks.append(callback)

    # ============================================
    # REST API Additional Methods
    # ============================================

    async def fetch_time_series(
        self,
        base: str,
        quote: str,
        interval: str = "1min",  # 1min, 5min, 15min, 30min, 45min, 1h, 2h, 4h, 1day, 1week, 1month
        outputsize: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[ExchangeRate]:
        """Busca série temporal via REST"""
        rates = []

        if not self.api_key:
            return rates

        try:
            symbol = f"{base}/{quote}" if base != "BRL" else f"{quote}/{base}"

            params = {
                "symbol": symbol,
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self.api_key
            }
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            self._rate_limit_wait()
            response = await self.client.get(f"{self.base_url}/time_series", params=params)
            response.raise_for_status()
            data = response.json()

            if "values" in data:
                for item in data["values"]:
                    try:
                        close = Decimal(str(item.get("close", 0)))
                        if close <= 0:
                            continue

                        timestamp = datetime.strptime(item["datetime"], "%Y-%m-%d %H:%M:%S")

                        rate = close
                        if base == "BRL":
                            rate = Decimal("1") / close

                        exchange_rate = self._create_rate(
                            base=base,
                            quote=quote,
                            rate=float(rate),
                            rate_type=RateType.COMMERCIAL,
                            raw_data=item
                        )
                        exchange_rate.timestamp = timestamp
                        rates.append(exchange_rate)

                    except (ValueError, KeyError, TypeError):
                        continue

        except Exception:
            pass

        return rates

    async def close(self):
        await self.disconnect_websocket()
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()