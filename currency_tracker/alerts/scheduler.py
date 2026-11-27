# ============================================
# CurrencyTracker - Alerts Scheduler
# ============================================

import asyncio
import signal
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
import structlog

from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.models import Alert, AlertHistory
from currency_tracker.storage.influxdb_client import InfluxDBClient
from currency_tracker.config.settings import get_settings

logger = structlog.get_logger()


class AlertsScheduler:
    """Agendador de verificação de alertas"""

    def __init__(self):
        self.settings = get_settings()
        self.repository = RateRepository()
        self.influxdb = InfluxDBClient()
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._last_check: Dict[int, datetime] = {}

    async def initialize(self):
        """Inicializa conexões"""
        await self.repository.initialize()
        await self.influxdb.connect()

    async def start(self):
        """Inicia scheduler"""
        if self._running:
            return

        self._running = True
        logger.info("Starting alerts scheduler")

        check_task = asyncio.create_task(self._check_loop())
        self._tasks.append(check_task)

    async def stop(self):
        """Para scheduler"""
        if not self._running:
            return

        logger.info("Stopping alerts scheduler")
        self._running = False

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        await self.repository.close()
        await self.influxdb.close()

    async def _check_loop(self):
        """Loop principal de verificação"""
        while self._running:
            try:
                alerts = await self.repository.get_active_alerts()

                for alert in alerts:
                    await self._check_alert(alert)

                await asyncio.sleep(60)  # Verifica a cada minuto

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Alert check loop error", error=str(e))
                await asyncio.sleep(60)

    async def _check_alert(self, alert: Alert):
        """Verifica um alerta específico"""
        # Verifica cooldown
        last_check = self._last_check.get(alert.id)
        if last_check:
            elapsed = (datetime.utcnow() - last_check).total_seconds()
            if elapsed < alert.check_interval_seconds:
                return

        self._last_check[alert.id] = datetime.utcnow()

        # Busca taxa atual
        base = alert.base_currency.code if alert.base_currency else "BRL"
        quote = alert.quote_currency.code if alert.quote_currency else "USD"

        try:
            rate = await self.repository.get_latest_rate(base, quote)
            if not rate:
                return

            current_rate = rate.rate
            threshold = alert.threshold_value
            triggered = False
            condition_met = ""

            # Avalia condição
            if alert.condition_type == "above" and current_rate > threshold:
                triggered = True
                condition_met = f"Rate {current_rate} > {threshold}"
            elif alert.condition_type == "below" and current_rate < threshold:
                triggered = True
                condition_met = f"Rate {current_rate} < {threshold}"
            elif alert.condition_type == "change_pct":
                # Precisa comparar com taxa anterior
                history = await self.repository.get_rates_history(
                    base, quote,
                    start_date=datetime.utcnow() - timedelta(hours=1),
                    limit=2
                )
                if len(history) >= 2:
                    prev_rate = history[1].rate
                    change_pct = ((current_rate - prev_rate) / prev_rate) * 100
                    if abs(change_pct) >= float(threshold):
                        triggered = True
                        condition_met = f"Change {change_pct:.2f}% >= {threshold}%"
            elif alert.condition_type == "volatility":
                # Calcula volatilidade recente
                history = await self.repository.get_rates_history(
                    base, quote,
                    start_date=datetime.utcnow() - timedelta(hours=24),
                    limit=100
                )
                if len(history) >= 10:
                    rates = [float(r.rate) for r in history]
                    import numpy as np
                    vol = np.std(np.diff(np.log(rates))) * np.sqrt(252) * 100
                    if vol >= float(threshold):
                        triggered = True
                        condition_met = f"Volatility {vol:.2f}% >= {threshold}%"

            if triggered:
                await self._trigger_alert(alert, current_rate, condition_met)

        except Exception as e:
            logger.error("Alert check failed", alert_id=alert.id, error=str(e))

    async def _trigger_alert(
        self,
        alert: Alert,
        current_rate: Decimal,
        condition_met: str
    ):
        """Dispara notificações do alerta"""
        logger.info("Alert triggered",
                   alert=alert.name,
                   pair=f"{alert.base_currency.code}/{alert.quote_currency.code}",
                   rate=current_rate,
                   condition=condition_met)

        # Salva histórico
        history = AlertHistory(
            alert_id=alert.id,
            current_rate=current_rate,
            threshold_value=alert.threshold_value,
            condition_met=condition_met,
            telegram_sent=False,
            discord_sent=False,
            email_sent=False,
            webhook_sent=False
        )
        await self.repository.save_alert_history(history)

        # Envia notificações (placeholder)
        if alert.notify_telegram:
            await self._send_telegram(alert, current_rate, condition_met)
            history.telegram_sent = True

        if alert.notify_discord:
            await self._send_discord(alert, current_rate, condition_met)
            history.discord_sent = True

        if alert.notify_email:
            await self._send_email(alert, current_rate, condition_met)
            history.email_sent = True

        if alert.notify_webhook and alert.webhook_url:
            await self._send_webhook(alert, current_rate, condition_met)
            history.webhook_sent = True

        # Atualiza histórico
        await self.repository.save_alert_history(history)

        # Atualiza last_triggered do alerta
        alert.last_triggered = datetime.utcnow()

    async def _send_telegram(self, alert: Alert, rate: Decimal, condition: str):
        """Envia notificação Telegram"""
        # TODO: Implementar com python-telegram-bot
        logger.info("Telegram notification sent", alert=alert.name)

    async def _send_discord(self, alert: Alert, rate: Decimal, condition: str):
        """Envia notificação Discord"""
        # TODO: Implementar com discord.py ou webhook
        logger.info("Discord notification sent", alert=alert.name)

    async def _send_email(self, alert: Alert, rate: Decimal, condition: str):
        """Envia email"""
        # TODO: Implementar com aiosmtplib
        logger.info("Email notification sent", alert=alert.name)

    async def _send_webhook(self, alert: Alert, rate: Decimal, condition: str):
        """Envia webhook"""
        # TODO: Implementar com httpx
        logger.info("Webhook notification sent", alert=alert.name)


async def main():
    """Entry point standalone"""
    settings = get_settings()

    scheduler = AlertsScheduler()

    await scheduler.initialize()

    def signal_handler():
        logger.info("Shutdown signal received")
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


if __name__ == "__main__":
    asyncio.run(main())