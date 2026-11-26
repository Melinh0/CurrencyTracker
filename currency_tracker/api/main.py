from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import structlog
from currency_tracker.api.dependencies import close_connections
from currency_tracker.config.settings import get_settings
structlog.configure(processors=[structlog.stdlib.filter_by_level, structlog.stdlib.add_logger_name, structlog.stdlib.add_log_level, structlog.stdlib.PositionalArgumentsFormatter(), structlog.processors.TimeStamper(fmt='iso'), structlog.processors.StackInfoRenderer(), structlog.processors.format_exc_info, structlog.processors.UnicodeDecoder(), structlog.processors.JSONRenderer()], context_class=dict, logger_factory=structlog.stdlib.LoggerFactory(), cache_logger_on_first_use=True)
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info('Starting CurrencyTracker API', version='0.1.0')
    try:
        from fastapi_cache3 import FastAPICache
        from fastapi_cache3.backends.inmemory import InMemoryBackend
        FastAPICache.init(InMemoryBackend(), prefix='currency-tracker-cache')
        logger.info('Cache initialized')
    except Exception as e:
        logger.warning('Cache init failed, continuing without cache', error=str(e))
    yield
    logger.info('Shutting down CurrencyTracker API')
    await close_connections()

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title='CurrencyTracker API', description='Real-time exchange rate monitoring and prediction API', version='0.1.0', docs_url='/docs' if settings.features.enable_api_docs else None, redoc_url='/redoc' if settings.features.enable_api_docs else None, openapi_url='/openapi.json' if settings.features.enable_api_docs else None, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    api_prefix = settings.api_v1_prefix
    from currency_tracker.api.routes.rates import router as rates_router
    from currency_tracker.api.routes.predictions import router as predictions_router
    app.include_router(rates_router, prefix=api_prefix)
    app.include_router(predictions_router, prefix=api_prefix)

    @app.get('/')
    async def root():
        return {'name': 'CurrencyTracker API', 'version': '0.1.0', 'description': 'Real-time exchange rate monitoring and prediction', 'docs': f'{api_prefix}/docs' if settings.features.enable_api_docs else 'disabled'}
    return app
app = create_app()
if __name__ == '__main__':
    import uvicorn
    settings = get_settings()
    uvicorn.run('currency_tracker.api.main:app', host='0.0.0.0', port=8000, reload=settings.debug, log_config=None)
