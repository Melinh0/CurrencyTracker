from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from currency_tracker.api.schemas import AlertResponse
router = APIRouter(prefix='/alerts', tags=['Alerts'])

@router.get('/', response_model=List[AlertResponse], summary='List alerts')
async def list_alerts(active_only: bool=Query(default=True)):
    return []

@router.get('/{alert_id}', response_model=AlertResponse, summary='Get alert details')
async def get_alert(alert_id: int):
    raise HTTPException(status_code=501, detail='Not implemented yet')

@router.delete('/{alert_id}', summary='Delete alert')
async def delete_alert(alert_id: int):
    raise HTTPException(status_code=501, detail='Not implemented yet')

@router.get('/{alert_id}/history', summary='Get alert history')
async def get_alert_history(alert_id: int, limit: int=Query(default=50, le=1000)):
    raise HTTPException(status_code=501, detail='Not implemented yet')
