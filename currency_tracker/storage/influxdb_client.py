# ============================================
# CurrencyTracker - InfluxDB Client
# ============================================

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, AsyncGenerator
from influxdb_client import InfluxDBClient as InfluxClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
from influxdb_client.client.query_api import QueryApi
import structlog

from currency_tracker.collector.sources import ExchangeRate
from currency_tracker.config.settings import get_settings

logger = structlog.get_logger()


class InfluxDBClient:
    """Cliente InfluxDB para dados de série temporal"""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        org: Optional[str] = None,
        bucket: Optional[str] = None,
        bucket_predictions: Optional[str] = None
    ):
        self.settings = get_settings()

        self.url = url or self.settings.influxdb.url
        self.token = token or self.settings.influxdb.token
        self.org = org or self.settings.influxdb.org
        self.bucket = bucket or self.settings.influxdb.bucket
        self.bucket_predictions = bucket_predictions or self.settings.influxdb.bucket_predictions

        self._client: Optional[InfluxClient] = None
        self._write_api = None
        self._query_api: Optional[QueryApi] = None
        self._connected = False

    async def connect(self):
        """Conecta ao InfluxDB"""
        if self._connected:
            return

        try:
            self._client = InfluxClient(
                url=self.url,
                token=self.token,
                org=self.org,
                timeout=30000
            )

            # Write API assíncrono para alta performance
            self._write_api = self._client.write_api(
                write_options=WriteOptions(
                    batch_size=5000,
                    flush_interval=1000,
                    jitter_interval=2000,
                    retry_interval=5000,
                    max_retries=3,
                    max_retry_delay=30000,
                    exponential_base=2
                )
            )

            self._query_api = self._client.query_api()

            # Testa conexão
            buckets_api = self._client.buckets_api()
            buckets = buckets_api.find_buckets().buckets
            bucket_names = [b.name for b in buckets]

            if self.bucket not in bucket_names:
                logger.warning("Bucket not found", bucket=self.bucket, available=bucket_names)

            if self.bucket_predictions not in bucket_names:
                logger.warning("Predictions bucket not found", bucket=self.bucket_predictions, available=bucket_names)

            self._connected = True
            logger.info("InfluxDB connected", url=self.url, org=self.org, bucket=self.bucket)

        except Exception as e:
            logger.error("InfluxDB connection failed", error=str(e))
            raise

    async def close(self):
        """Fecha conexão"""
        if self._write_api:
            self._write_api.close()
        if self._client:
            self._client.close()
        self._connected = False
        logger.info("InfluxDB disconnected")

    def _ensure_connected(self):
        if not self._connected:
            raise RuntimeError("InfluxDB not connected. Call connect() first.")

    # ============================================
    # Write Operations
    # ============================================

    async def write_rate(self, rate: ExchangeRate):
        """Escreve uma taxa no InfluxDB"""
        self._ensure_connected()

        try:
            point = Point("exchange_rates") \
                .tag("base", rate.base_currency) \
                .tag("quote", rate.quote_currency) \
                .tag("source", rate.source) \
                .tag("type", rate.rate_type.value) \
                .field("rate", float(rate.rate))

            if rate.bid:
                point = point.field("bid", float(rate.bid))
            if rate.ask:
                point = point.field("ask", float(rate.ask))
            if rate.spread:
                point = point.field("spread", float(rate.spread))

            point = point.time(rate.timestamp)

            # Write assíncrono (non-blocking)
            self._write_api.write(bucket=self.bucket, org=self.org, record=point)

        except Exception as e:
            logger.error("Failed to write rate to InfluxDB", error=str(e), rate=rate.to_dict())
            raise

    async def write_rates_batch(self, rates: List[ExchangeRate]):
        """Escreve múltiplas taxas em batch"""
        self._ensure_connected()

        if not rates:
            return

        try:
            points = []
            for rate in rates:
                point = Point("exchange_rates") \
                    .tag("base", rate.base_currency) \
                    .tag("quote", rate.quote_currency) \
                    .tag("source", rate.source) \
                    .tag("type", rate.rate_type.value) \
                    .field("rate", float(rate.rate))

                if rate.bid:
                    point = point.field("bid", float(rate.bid))
                if rate.ask:
                    point = point.field("ask", float(rate.ask))
                if rate.spread:
                    point = point.field("spread", float(rate.spread))

                point = point.time(rate.timestamp)
                points.append(point)

            self._write_api.write(bucket=self.bucket, org=self.org, record=points)
            logger.debug("Batch written to InfluxDB", count=len(points))

        except Exception as e:
            logger.error("Failed to write batch to InfluxDB", error=str(e), count=len(rates))
            raise

    async def write_prediction(
        self,
        base: str,
        quote: str,
        model_name: str,
        prediction_timestamp: datetime,
        predicted_rate: float,
        lower_bound: Optional[float] = None,
        upper_bound: Optional[float] = None,
        confidence_level: float = 95.0,
        horizon_days: Optional[int] = None
    ):
        """Escreve previsão no bucket de predições"""
        self._ensure_connected()

        try:
            point = Point("predictions") \
                .tag("base", base) \
                .tag("quote", quote) \
                .tag("model", model_name) \
                .field("predicted_rate", predicted_rate)

            if lower_bound is not None:
                point = point.field("lower_bound", lower_bound)
            if upper_bound is not None:
                point = point.field("upper_bound", upper_bound)
            if horizon_days:
                point = point.field("horizon_days", horizon_days)

            point = point.field("confidence_level", confidence_level) \
                .time(prediction_timestamp)

            self._write_api.write(bucket=self.bucket_predictions, org=self.org, record=point)

        except Exception as e:
            logger.error("Failed to write prediction to InfluxDB", error=str(e))
            raise

    async def flush(self):
        """Força flush do buffer de escrita"""
        if self._write_api:
            self._write_api.flush()

    # ============================================
    # Query Operations
    # ============================================

    async def query_rates(
        self,
        base: str,
        quote: str,
        start: datetime,
        end: Optional[datetime] = None,
        source: Optional[str] = None,
        aggregate: Optional[str] = None,  # mean, min, max, last
        window: Optional[str] = None      # 1m, 5m, 1h, 1d
    ) -> List[Dict[str, Any]]:
        """Consulta taxas históricas"""
        self._ensure_connected()

        end = end or datetime.utcnow()
        start_str = start.isoformat() + "Z"
        end_str = end.isoformat() + "Z"

        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start_str}, stop: {end_str})
          |> filter(fn: (r) => r._measurement == "exchange_rates")
          |> filter(fn: (r) => r.base == "{base}" and r.quote == "{quote}")
        '''

        if source:
            flux += f'  |> filter(fn: (r) => r.source == "{source}")\n'

        if aggregate and window:
            flux += f'  |> aggregateWindow(every: {window}, fn: {aggregate}, createEmpty: false)\n'

        flux += '  |> sort(columns: ["_time"])\n'

        try:
            result = self._query_api.query_data_frame(flux)
            if result.empty:
                return []

            # Converte DataFrame para lista de dicts
            records = []
            for _, row in result.iterrows():
                records.append({
                    "time": row["_time"],
                    "base": row.get("base"),
                    "quote": row.get("quote"),
                    "source": row.get("source"),
                    "type": row.get("type"),
                    "field": row["_field"],
                    "value": row["_value"]
                })
            return records

        except Exception as e:
            logger.error("InfluxDB query failed", error=str(e), flux=flux)
            raise

    async def query_latest_rate(self, base: str, quote: str, source: Optional[str] = None) -> Optional[Dict]:
        """Busca taxa mais recente"""
        self._ensure_connected()

        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -1h)
          |> filter(fn: (r) => r._measurement == "exchange_rates")
          |> filter(fn: (r) => r.base == "{base}" and r.quote == "{quote}")
        '''

        if source:
            flux += f'  |> filter(fn: (r) => r.source == "{source}")\n'

        flux += '  |> last()\n'

        try:
            result = self._query_api.query_data_frame(flux)
            if result.empty:
                return None

            row = result.iloc[-1]
            return {
                "time": row["_time"],
                "base": row.get("base"),
                "quote": row.get("quote"),
                "source": row.get("source"),
                "type": row.get("type"),
                "field": row["_field"],
                "value": row["_value"]
            }

        except Exception as e:
            logger.error("Failed to query latest rate", error=str(e))
            return None

    async def query_statistics(
        self,
        base: str,
        quote: str,
        start: datetime,
        end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Calcula estatísticas via Flux"""
        self._ensure_connected()

        end = end or datetime.utcnow()
        start_str = start.isoformat() + "Z"
        end_str = end.isoformat() + "Z"

        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start_str}, stop: {end_str})
          |> filter(fn: (r) => r._measurement == "exchange_rates")
          |> filter(fn: (r) => r.base == "{base}" and r.quote == "{quote}")
          |> filter(fn: (r) => r._field == "rate")
          |> reduce(
              identity: {{count: 0.0, sum: 0.0, min: 0.0, max: 0.0, sum_sq: 0.0}},
              fn: (r, accumulator) => ({{
                  count: accumulator.count + 1.0,
                  sum: accumulator.sum + r._value,
                  min: if accumulator.count == 0.0 then r._value else min(accumulator.min, r._value),
                  max: if accumulator.count == 0.0 then r._value else max(accumulator.max, r._value),
                  sum_sq: accumulator.sum_sq + r._value * r._value
              }})
          )
          |> map(fn: (r) => ({{
              count: r.count,
              mean: r.sum / r.count,
              min: r.min,
              max: r.max,
              stddev: sqrt((r.sum_sq / r.count) - (r.sum / r.count) * (r.sum / r.count))
          }}))
        '''

        try:
            result = self._query_api.query_data_frame(flux)
            if result.empty:
                return {}

            row = result.iloc[-1]
            return {
                "pair": f"{base}/{quote}",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "count": int(row.get("count", 0)),
                "mean": float(row.get("mean", 0)),
                "min": float(row.get("min", 0)),
                "max": float(row.get("max", 0)),
                "stddev": float(row.get("stddev", 0))
            }

        except Exception as e:
            logger.error("Failed to query statistics", error=str(e))
            return {}

    async def query_correlation(
        self,
        base: str,
        quotes: List[str],
        start: datetime,
        end: Optional[datetime] = None,
        window: str = "1h"
    ) -> Dict[str, float]:
        """Calcula correlação entre pares"""
        # Esta é uma query complexa - simplificada aqui
        # Em produção, usar Flux join ou calcular no Python
        correlations = {}
        for quote in quotes:
            if quote == base:
                continue
            # Placeholder - implementar correlação real
            correlations[f"{base}/{quote}"] = 0.0
        return correlations

    # ============================================
    # Utility Methods
    # ============================================

    async def health_check(self) -> bool:
        """Verifica saúde da conexão"""
        try:
            if not self._connected:
                return False
            # Ping simples
            self._client.ping()
            return True
        except Exception:
            return False

    def get_client(self) -> InfluxClient:
        """Retorna cliente bruto para operações avançadas"""
        self._ensure_connected()
        return self._client