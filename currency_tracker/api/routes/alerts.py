# ============================================
# CurrencyTracker - Alerts API Routes
# ============================================

from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status

from currency_tracker.api.schemas import (
    AlertBase,
    AlertResponse,
    ErrorResponse
)
from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.models import Alert, AlertHistory
from currency_tracker.api.dependencies import get_rate_repo

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post(
    "/",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert",
    description="Creates a new price alert for a currency pair"
)
async def create_alert(
    alert: AlertBase,
    repo: RateRepository = Depends(get_rate_repo)
):
    """Cria novo alerta"""
    # Verifica se moedas existem
    base_cur = await repo.get_currency(alert.base_currency)
    quote_cur = await repo.get_currency(alert.quote_currency)

    if not base_cur or not quote_cur:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid currency codes"
        )

    db_alert = Alert(
        name=alert.name,
        description=alert.description,
        base_currency_id=base_cur.id,
        quote_currency_id=quote_cur.id,
        condition_type=alert.condition_type,
        threshold_value=alert.threshold_value,
        check_interval_seconds=alert.check_interval_seconds,
        cooldown_seconds=alert.cooldown_seconds,
        priority=alert.priority,
        notify_telegram=alert.notify_telegram,
        notify_discord=alert.notify_discord,
        notify_email=alert.notify_email,
        notify_webhook=alert.notify_webhook,
        webhook_url=alert.webhook_url,
        is_active=True
    )

    saved = await repo.save_alert(db_alert)
    return AlertResponse.model_validate(saved)


@router.get(
    "/",
    response_model=List[AlertResponse],
    summary="List alerts",
    description="Returns all configured alerts"
)
async def list_alerts(
    active_only: bool = Query(default=True),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Lista alertas"""
    if active_only:
        alerts = await repo.get_active_alerts()
    else:
        # Precisaria de método para listar todos
        alerts = await repo.get_active_alerts()

    return [AlertResponse.model_validate(a) for a in alerts]


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get alert details",
    description="Returns details for a specific alert"
)
async def get_alert(
    alert_id: int,
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca detalhes de um alerta"""
    # Precisaria implementar get_alert no repository
    # Por enquanto retorna 404
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented yet"
    )


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete alert",
    description="Deactivates an alert (soft delete)"
)
async def delete_alert(
    alert_id: int,
    repo: RateRepository = Depends(get_rate_repo)
):
    """Desativa alerta"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented yet"
    )


@router.get(
    "/{alert_id}/history",
    summary="Get alert history",
    description="Returns trigger history for an alert"
)
async def get_alert_history(
    alert_id: int,
    limit: int = Query(default=50, le=1000),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Histórico de disparos do alerta"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented yet"
    )