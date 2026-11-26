import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import structlog
from currency_tracker.ml.training.pipeline import TrainingPipeline, TrainingConfig
from currency_tracker.storage.repository import RateRepository
from currency_tracker.config.settings import get_settings
logger = structlog.get_logger()

class MLTrainingScheduler:

    def __init__(self, currencies: List[str], base_currency: str='BRL', retrain_interval_hours: int=24, model_types: List[str]=None, min_training_samples: int=100):
        self.settings = get_settings()
        self.currencies = currencies
        self.base_currency = base_currency
        self.retrain_interval_hours = retrain_interval_hours
        self.model_types = model_types or ['ridge', 'random_forest', 'xgboost', 'lightgbm']
        self.min_training_samples = min_training_samples
        self.repository = RateRepository()
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._last_training: Dict[str, datetime] = {}
        self._training_stats: Dict[str, Dict] = {}

    async def initialize(self):
        await self.repository.initialize()
        for currency in self.currencies:
            model = await self.repository.get_active_model(currency, self.base_currency)
            if model and model.trained_at:
                self._last_training[currency] = model.trained_at

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info('Starting ML training scheduler', currencies=self.currencies, interval_hours=self.retrain_interval_hours)
        check_task = asyncio.create_task(self._check_and_train_loop())
        self._tasks.append(check_task)
        stats_task = asyncio.create_task(self._stats_loop())
        self._tasks.append(stats_task)

    async def stop(self):
        if not self._running:
            return
        logger.info('Stopping ML training scheduler')
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self.repository.close()

    async def _check_and_train_loop(self):
        while self._running:
            try:
                for currency in self.currencies:
                    await self._check_and_train_currency(currency)
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error('Training loop error', error=str(e))
                await asyncio.sleep(300)

    async def _check_and_train_currency(self, currency: str):
        last_train = self._last_training.get(currency)
        if last_train:
            elapsed = datetime.utcnow() - last_train
            if elapsed < timedelta(hours=self.retrain_interval_hours):
                return
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)
        rates = await self.repository.get_rates_history(base=self.base_currency, quote=currency, start_date=start_date, end_date=end_date, limit=self.min_training_samples + 100)
        if len(rates) < self.min_training_samples:
            logger.warning('Insufficient data for training', currency=currency, samples=len(rates), required=self.min_training_samples)
            return
        logger.info('Starting training', currency=currency, samples=len(rates))
        try:
            config = TrainingConfig(target_currency=currency, base_currency=self.base_currency, model_types=self.model_types, min_training_samples=self.min_training_samples)
            pipeline = TrainingPipeline(config)
            pipeline.repository = self.repository
            result = await pipeline.run()
            self._last_training[currency] = datetime.utcnow()
            self._training_stats[currency] = {'last_training': self._last_training[currency].isoformat(), 'result': result}
            logger.info('Training completed', currency=currency, **result)
        except Exception as e:
            logger.error('Training failed', currency=currency, error=str(e))

    async def _stats_loop(self):
        while self._running:
            try:
                await asyncio.sleep(3600)
                for currency in self.currencies:
                    last = self._last_training.get(currency)
                    if last:
                        elapsed = datetime.utcnow() - last
                        logger.info('ML Training status', currency=currency, last_training=last.isoformat(), hours_since=elapsed.total_seconds() / 3600)
                    else:
                        logger.info('ML Training status', currency=currency, last_training='never')
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error('Stats loop error', error=str(e))

    def get_stats(self) -> Dict:
        return {'running': self._running, 'currencies': self.currencies, 'retrain_interval_hours': self.retrain_interval_hours, 'last_training': {k: v.isoformat() if isinstance(v, datetime) else v for k, v in self._last_training.items()}, 'training_stats': self._training_stats}

    async def force_train(self, currency: str) -> Dict:
        logger.info('Force training requested', currency=currency)
        config = TrainingConfig(target_currency=currency, base_currency=self.base_currency, model_types=self.model_types, min_training_samples=self.min_training_samples)
        pipeline = TrainingPipeline(config)
        pipeline.repository = self.repository
        result = await pipeline.run()
        self._last_training[currency] = datetime.utcnow()
        self._training_stats[currency] = {'last_training': self._last_training[currency].isoformat(), 'result': result}
        return result

async def main():
    settings = get_settings()
    currencies = settings.tracked_currency_list
    scheduler = MLTrainingScheduler(currencies=currencies, base_currency=settings.base_currency, retrain_interval_hours=settings.ml.retrain_interval_hours, min_training_samples=settings.ml.min_training_samples)
    await scheduler.initialize()

    def signal_handler():
        logger.info('Shutdown signal received')
        asyncio.create_task(scheduler.stop())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass
    try:
        await scheduler.start()
        while scheduler._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await scheduler.stop()
if __name__ == '__main__':
    asyncio.run(main())
