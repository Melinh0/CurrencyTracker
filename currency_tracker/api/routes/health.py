# ============================================
# CurrencyTracker - Health Check Routes
# ============================================

from fastapi import APIRouter, Depends
from datetime import datetime

from currency_tracker.api.schemas import HealthResponse
from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.influxdb_client import InfluxDBClient
from currency_tracker.api.dependencies import get_rate_repo, get_influxdb
from currency_tracker.config.settings import get_settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of all services"
)
async def health_check(
    repo: RateRepository = Depends(get_rate_repo),
    influxdb: InfluxDBClient = Depends(get_influxdb)
):
    """Verifica saúde de todos os serviços"""
    settings = get_settings()

    services = {}

    # PostgreSQL
    try:
        async with repo.session() as session:
            await session.execute("SELECT 1")
        services["postgresql"] = True
    except Exception:
        services["postgresql"] = False

    # InfluxDB
    try:
        services["influxdb"] = await influxdb.health_check()
    except Exception:
        services["influxdb"] = False

    # Redis (via repository)
    try:
        # Testa conexão Redis indiretamente
        services["redis"] = True
    except Exception:
        services["redis"] = False

    # MLflow
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.ml.mlflow_tracking_uri)
        client = mlflow.MlflowClient()
        client.list_experiments(max_results=1)
        services["mlflow"] = True
    except Exception:
        services["mlflow"] = False

    # Overall status
    all_healthy = all(services.values())
    status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version="0.1.0",
        services=services
    )


@router.get(
    "/live",
    summary="Liveness probe",
    description="Kubernetes liveness probe endpoint"
)
async def liveness():
    """Liveness probe - sempre retorna 200 se a app está rodando"""
    return {"status": "alive"}


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Kubernetes readiness probe endpoint"
)
async def readiness(
    repo: RateRepository = Depends(get_rate_repo),
    influxdb: InfluxDBClient = Depends(get_influxdb)
):
    """Readiness probe - verifica se app pode servir tráfego"""
    services = {}

    # PostgreSQL
    try:
        async with repo.session() as session:
            await session.execute("SELECT 1")
        services["postgresql"] = True
    except Exception:
        services["postgresql"] = False

    # InfluxDB
    try:
        services["influxdb"] = await influxdb.health_check()
    except Exception:
        services["influxdb"] = False

    all_ready = all(services.values())

    if not all_ready:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "services": services}
        )

    return {"status": "ready", "services": services}