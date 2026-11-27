# ============================================
# CurrencyTracker - Collector Scheduler
# ============================================

import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
import structlog

from currency_tracker.collector.factory import source_factory
from currency_tracker.collector.validator import RateValidator, CrossSourceValidator
from currency_tracker.collector.sources import ExchangeRate, CollectionResult
from currency_tracker.config.settings import get_settings, get_currency_config
from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.influxdb_client import InfluxDBClient

logger = structlog.get_logger()


@dataclass
class CollectionJob:
    """Job de coleta agendado"""
    name: str
    base_currency: str
    quote_currencies: List[str]
    interval_seconds: int
    sources: List[str] = field(default_factory=list)
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    callback: Optional[Callable] = None


class CollectorScheduler:
    """Agendador de coleta de taxas de câmbio"""

    def __init__(
        self,
        base_currency: str = "BRL",
        quote_currencies: Optional[List[str]] = None,
        interval_seconds: int = 60,
        sources: Optional[List[str]] = None
    ):
        self.settings = get_settings()
        self.currency_config = get_currency_config()

        self.base_currency = base_currency
        self.quote_currencies = quote_currencies or self.settings.tracked_currency_list
        self.interval_seconds = interval_seconds
        self.source_names = sources or ["awesomeapi", "exchangerate", "yahoo"]

        # Componentes
        self.validator = RateValidator()
        self.cross_validator = CrossSourceValidator()
        self.repository = RateRepository()
        self.influxdb = InfluxDBClient()

        # Estado
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._jobs: Dict[str, CollectionJob] = {}
        self._stats = {
            "total_collections": 0,
            "successful_collections": 0,
            "failed_collections": 0,
            "total_rates_collected": 0,
            "last_collection": None,
            "start_time": None
        }

        # Callbacks para alertas
        self._rate_callbacks: List[Callable[[ExchangeRate], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []

        # Setup default job
        self._setup_default_job()

    def _setup_default_job(self):
        """Configura job padrão"""
        job = CollectionJob(
            name="default",
            base_currency=self.base_currency,
            quote_currencies=self.quote_currencies,
            interval_seconds=self.interval_seconds,
            sources=self.source_names,
            enabled=True
        )
        self._jobs["default"] = job

    def add_job(self, job: CollectionJob):
        """Adiciona job personalizado"""
        self._jobs[job.name] = job

    def on_rate_collected(self, callback: Callable[[ExchangeRate], None]):
        """Registra callback para nova taxa coletada"""
        self._rate_callbacks.append(callback)

    def on_error(self, callback: Callable[[Exception], None]):
        """Registra callback para erros"""
        self._error_callbacks.append(callback)

    async def start(self):
        """Inicia o scheduler"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._stats["start_time"] = datetime.utcnow()

        logger.info(
            "Starting collector scheduler",
            base_currency=self.base_currency,
            quote_currencies=self.quote_currencies,
            interval_seconds=self.interval_seconds,
            sources=self.source_names
        )

        # Inicia tasks para cada job
        for job in self._jobs.values():
            if job.enabled:
                task = asyncio.create_task(self._run_job(job))
                self._tasks.append(task)

        # Task de health check
        health_task = asyncio.create_task(self._health_check_loop())
        self._tasks.append(health_task)

        # Task de estatísticas
        stats_task = asyncio.create_task(self._stats_loop())
        self._tasks.append(stats_task)

    async def stop(self):
        """Para o scheduler"""
        if not self._running:
            return

        logger.info("Stopping collector scheduler")
        self._running = False

        # Cancela todas as tasks
        for task in self._tasks:
            task.cancel()

        # Aguarda conclusão
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Fecha conexões
        await source_factory.close_all()
        await self.repository.close()
        await self.influxdb.close()

        logger.info("Scheduler stopped", stats=self.get_stats())

    async def _run_job(self, job: CollectionJob):
        """Loop principal de um job"""
        logger.info("Starting collection job", job=job.name, interval=job.interval_seconds)

        while self._running:
            try:
                job.last_run = datetime.utcnow()
                job.next_run = job.last_run + timedelta(seconds=job.interval_seconds)

                await self._collect_once(job)

                job.run_count += 1
                self._stats["total_collections"] += 1
                self._stats["successful_collections"] += 1
                self._stats["last_collection"] = job.last_run

            except Exception as e:
                job.error_count += 1
                self._stats["failed_collections"] += 1
                logger.error("Collection job error", job=job.name, error=str(e))
                for cb in self._error_callbacks:
                    try:
                        cb(e)
                    except Exception:
                        pass

            # Aguarda próximo ciclo
            if self._running:
                await asyncio.sleep(job.interval_seconds)

    async def _collect_once(self, job: CollectionJob):
        """Executa uma coleta única"""
        start_time = datetime.utcnow()

        # Obtém fontes para este job
        sources = []
        for name in job.sources:
            source = source_factory.create_source(name)
            if source:
                sources.append(source)

        if not sources:
            raise ValueError(f"No valid sources for job {job.name}")

        # Coleta de todas as fontes em paralelo
        collection_tasks = [
            source.fetch_rates(job.base_currency, job.quote_currencies)
            for source in sources
        ]

        results = await asyncio.gather(*collection_tasks, return_exceptions=True)

        # Processa resultados
        rates_by_source: Dict[str, List[ExchangeRate]] = {}
        all_errors = []

        for source, result in zip(sources, results):
            if isinstance(result, Exception):
                all_errors.append(f"{source.name}: {str(result)}")
                continue

            if isinstance(result, CollectionResult):
                rates_by_source[source.name] = result.rates
                all_errors.extend(result.errors)

        # Validação cruzada entre fontes
        cross_validation = self.cross_validator.validate_consensus(rates_by_source)
        consensus_rates = self.cross_validator.get_consensus_rate(rates_by_source)

        # Validação individual e persistência
        saved_count = 0
        for source_name, rates in rates_by_source.items():
            validation_results = cross_validation.get(source_name, [])

            for i, rate in enumerate(rates):
                # Validação individual
                validation = self.validator.validate(rate)

                # Adiciona warnings da validação cruzada
                if i < len(validation_results):
                    validation.warnings.extend(validation_results[i].warnings)

                if validation.valid:
                    # Salva no PostgreSQL
                    await self.repository.save_rate(rate)

                    # Salva no InfluxDB
                    await self.influxdb.write_rate(rate)

                    # Notifica callbacks
                    for cb in self._rate_callbacks:
                        try:
                            cb(rate)
                        except Exception:
                            pass

                    saved_count += 1
                else:
                    logger.warning(
                        "Rate validation failed",
                        source=source_name,
                        pair=f"{rate.base_currency}/{rate.quote_currency}",
                        errors=validation.errors,
                        warnings=validation.warnings
                    )

        # Salva taxas de consenso
        for pair, consensus_rate in consensus_rates.items():
            await self.repository.save_rate(consensus_rate)
            await self.influxdb.write_rate(consensus_rate)

        self._stats["total_rates_collected"] += saved_count

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            "Collection completed",
            job=job.name,
            duration_ms=duration_ms,
            sources=len(sources),
            rates_collected=saved_count,
            consensus_pairs=len(consensus_rates),
            errors=len(all_errors)
        )

    async def _health_check_loop(self):
        """Loop de health check das fontes"""
        while self._running:
            try:
                await asyncio.sleep(300)  # 5 minutos

                for name in self.source_names:
                    source = source_factory.get_source(name)
                    if source:
                        healthy = await source.health_check()
                        logger.info("Health check", source=name, healthy=healthy)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check error", error=str(e))

    async def _stats_loop(self):
        """Loop de log de estatísticas"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 1 minuto
                stats = self.get_stats()
                logger.info("Collector stats", **stats)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Stats loop error", error=str(e))

    def get_stats(self) -> Dict:
        """Retorna estatísticas atuais"""
        uptime = None
        if self._stats["start_time"]:
            uptime = (datetime.utcnow() - self._stats["start_time"]).total_seconds()

        return {
            **self._stats,
            "uptime_seconds": uptime,
            "running": self._running,
            "active_jobs": len([j for j in self._jobs.values() if j.enabled]),
            "queue_size": len(self._tasks)
        }

    async def collect_now(self) -> CollectionResult:
        """Força uma coleta imediata (para testes)"""
        job = self._jobs.get("default")
        if not job:
            raise ValueError("No default job configured")

        await self._collect_once(job)
        return CollectionResult(
            success=True,
            rates=[],
            errors=[],
            source="manual",
            duration_ms=0,
            timestamp=datetime.utcnow()
        )


# Função principal para execução standalone
async def main():
    """Entry point para execução direta"""
    settings = get_settings()

    scheduler = CollectorScheduler(
        base_currency=settings.base_currency,
        quote_currencies=settings.tracked_currency_list,
        interval_seconds=settings.scheduler.collection_interval_seconds,
        sources=["awesomeapi", "exchangerate", "yahoo"]
    )

    # Setup signal handlers
    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(scheduler.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows não suporta add_signal_handler
            pass

    try:
        await scheduler.start()
        # Mantém rodando até sinal de parada
        while scheduler._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main())