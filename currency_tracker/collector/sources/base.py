# ============================================
# CurrencyTracker - Base Source Class
# ============================================

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


class RateType(str, Enum):
    """Tipo de taxa de câmbio"""
    COMMERCIAL = "commercial"      # Taxa comercial (compra/venda)
    TOURISM = "tourism"            # Taxa turismo
    OFFICIAL = "official"          # Taxa oficial (PTAX)
    PARALLEL = "parallel"          # Taxa paralela/blue
    CRYPTO = "crypto"              # Criptomoeda


@dataclass
class ExchangeRate:
    """Taxa de câmbio coletada"""
    base_currency: str
    quote_currency: str
    rate: Decimal                    # 1 base = X quote (ex: 1 USD = 5.20 BRL)
    bid: Optional[Decimal] = None    # Preço de compra (bid)
    ask: Optional[Decimal] = None    # Preço de venda (ask)
    rate_type: RateType = RateType.COMMERCIAL
    source: str = ""
    timestamp: datetime = None
    raw_data: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.raw_data is None:
            self.raw_data = {}

    @property
    def spread(self) -> Optional[Decimal]:
        """Spread entre ask e bid"""
        if self.bid and self.ask and self.bid > 0:
            return ((self.ask - self.bid) / self.bid) * Decimal("100")
        return None

    @property
    def mid_rate(self) -> Decimal:
        """Taxa média (mid)"""
        if self.bid and self.ask:
            return (self.bid + self.ask) / Decimal("2")
        return self.rate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
            "rate": float(self.rate),
            "bid": float(self.bid) if self.bid else None,
            "ask": float(self.ask) if self.ask else None,
            "rate_type": self.rate_type.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "spread": float(self.spread) if self.spread else None,
        }

    def to_influx_line(self, measurement: str = "exchange_rates") -> str:
        """Converte para line protocol do InfluxDB"""
        tags = f"base={self.base_currency},quote={self.quote_currency},source={self.source},type={self.rate_type.value}"
        fields = f"rate={float(self.rate)}"
        if self.bid:
            fields += f",bid={float(self.bid)}"
        if self.ask:
            fields += f",ask={float(self.ask)}"
        if self.spread:
            fields += f",spread={float(self.spread)}"
        timestamp_ns = int(self.timestamp.timestamp() * 1_000_000_000)
        return f"{measurement},{tags} {fields} {timestamp_ns}"


@dataclass
class CollectionResult:
    """Resultado de uma coleta"""
    success: bool
    rates: List[ExchangeRate]
    errors: List[str]
    source: str
    duration_ms: float
    timestamp: datetime

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class BaseSource(ABC):
    """Classe base para fontes de dados de câmbio"""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        timeout: float = 30.0,
        rate_limit: float = 1.0  # requests per second
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.rate_limit = rate_limit
        self._last_request_time: Optional[datetime] = None

    @abstractmethod
    async def fetch_rates(self, base: str, quotes: List[str]) -> CollectionResult:
        """
        Busca taxas de câmbio para as moedas especificadas.

        Args:
            base: Moeda base (ex: "BRL")
            quotes: Lista de moedas de cotação (ex: ["USD", "EUR", "GBP"])

        Returns:
            CollectionResult com as taxas coletadas
        """
        pass

    @abstractmethod
    def parse_response(self, response: Any, base: str, quotes: List[str]) -> List[ExchangeRate]:
        """
        Converte resposta da API em lista de ExchangeRate.

        Args:
            response: Resposta bruta da API
            base: Moeda base
            quotes: Moedas solicitadas

        Returns:
            Lista de ExchangeRate parseadas
        """
        pass

    def _rate_limit_wait(self) -> None:
        """Aguarda se necessário para respeitar rate limit"""
        if self._last_request_time:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            min_interval = 1.0 / self.rate_limit if self.rate_limit > 0 else 0
            if elapsed < min_interval:
                import time
                time.sleep(min_interval - elapsed)
        self._last_request_time = datetime.utcnow()

    def _create_rate(
        self,
        base: str,
        quote: str,
        rate: float,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        rate_type: RateType = RateType.COMMERCIAL,
        raw_data: Dict = None
    ) -> ExchangeRate:
        """Cria um ExchangeRate com validação básica"""
        return ExchangeRate(
            base_currency=base,
            quote_currency=quote,
            rate=Decimal(str(rate)),
            bid=Decimal(str(bid)) if bid else None,
            ask=Decimal(str(ask)) if ask else None,
            rate_type=rate_type,
            source=self.name,
            raw_data=raw_data or {}
        )

    async def health_check(self) -> bool:
        """Verifica se a fonte está disponível"""
        try:
            result = await self.fetch_rates("USD", ["BRL"])
            return result.success and len(result.rates) > 0
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"