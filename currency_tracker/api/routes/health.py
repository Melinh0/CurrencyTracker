from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from currency_tracker.api.schemas import HealthResponse
from currency_tracker.storage.repository import RateRepository
from currency_tracker.api.dependencies import get_rate_repo
from currency_tracker.config.settings import get_settings
router = APIRouter(prefix='/health', tags=['Health'])

@router.get('/', response_model=HealthResponse, summary='Health check')
async def health_check(repo: RateRepository=Depends(get_rate_repo)):
    settings = get_settings()
    services = {}
    try:
        async with repo.session() as session:
            await session.execute('SELECT 1')
        services['database'] = True
    except Exception:
        services['database'] = False
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis.url)
        await redis_client.ping()
        await redis_client.close()
        services['redis'] = True
    except Exception:
        services['redis'] = False
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.ml.mlflow_tracking_uri)
        client = mlflow.MlflowClient()
        client.list_experiments(max_results=1)
        services['mlflow'] = True
    except Exception:
        services['mlflow'] = False
    all_healthy = all(services.values()) or any(services.values())
    status = 'healthy' if all_healthy else 'degraded'
    return HealthResponse(status=status, timestamp=datetime.utcnow(), version='0.1.0', services=services)

@router.get('/live', summary='Liveness probe')
async def liveness():
    return {'status': 'alive'}

@router.get('/ready', summary='Readiness probe')
async def readiness(repo: RateRepository=Depends(get_rate_repo)):
    services = {}
    try:
        async with repo.session() as session:
            await session.execute('SELECT 1')
        services['database'] = True
    except Exception:
        services['database'] = False
    all_ready = services.get('database', False)
    if not all_ready:
        raise HTTPException(status_code=503, detail={'status': 'not ready', 'services': services})
    return {'status': 'ready', 'services': services}
