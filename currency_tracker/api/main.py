# ============================================
# CurrencyTracker - FastAPI Application
# ============================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
import redis.asyncio as redis
import structlog

from currency_tracker.api.routes import rates, predictions, currencies, alerts, health
from currency_tracker.api.dependencies import close_connections
from currency_tracker.config.settings import get_settings

# Configuração de logging estruturado
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    settings = get_settings()

    # Startup
    logger.info("Starting CurrencyTracker API", version="0.1.0")

    # Inicializa cache Redis
    try:
        redis_client = redis.from_url(settings.redis.url, encoding="utf-8", decode_responses=True)
        FastAPICache.init(RedisBackend(redis_client), prefix="currency-tracker-cache")
        logger.info("Redis cache initialized")
    except Exception as e:
        logger.warning("Redis cache not available", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down CurrencyTracker API")
    await close_connections()


def create_app() -> FastAPI:
    """Cria instância da aplicação FastAPI"""
    settings = get_settings()

    app = FastAPI(
        title="CurrencyTracker API",
        description="Real-time exchange rate monitoring and prediction API",
        version="0.1.0",
        docs_url="/docs" if settings.features.enable_api_docs else None,
        redoc_url="/redoc" if settings.features.enable_api_docs else None,
        openapi_url="/openapi.json" if settings.features.enable_api_docs else None,
        lifespan=lifespan
    )

    # Middlewares
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configurar adequadamente em produção
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Prefixo da API v1
    api_prefix = settings.api_v1_prefix

    # Inclui routers
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(rates.router, prefix=api_prefix)
    app.include_router(predictions.router, prefix=api_prefix)
    app.include_router(currencies.router, prefix=api_prefix)
    app.include_router(alerts.router, prefix=api_prefix)

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "CurrencyTracker API",
            "version": "0.1.0",
            "description": "Real-time exchange rate monitoring and prediction",
            "docs": f"{api_prefix}/docs" if settings.features.enable_api_docs else "disabled"
        }

    return app


# Instância global para uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "currency_tracker.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_config=None  # Usa structlog
    )