# ============================================
# CurrencyTracker - Currencies API Routes
# ============================================

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from currency_tracker.api.schemas import (
    CurrencyResponse,
    DataSourceResponse,
    ErrorResponse
)
from currency_tracker.storage.repository import RateRepository
from currency_tracker.api.dependencies import get_rate_repo
from currency_tracker.config.settings import get_currency_config

router = APIRouter(prefix="/currencies", tags=["Currencies"])


@router.get(
    "/",
    response_model=List[CurrencyResponse],
    summary="List all currencies",
    description="Returns all configured currencies"
)
async def list_currencies(
    active_only: bool = Query(default=True),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Lista todas as moedas"""
    currencies = await repo.get_all_currencies(active_only)
    return [CurrencyResponse.model_validate(c) for c in currencies]


@router.get(
    "/{code}",
    response_model=CurrencyResponse,
    summary="Get currency details",
    description="Returns details for a specific currency"
)
async def get_currency(
    code: str,
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca detalhes de uma moeda"""
    currency = await repo.get_currency(code)

    if not currency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Currency {code} not found"
        )

    return CurrencyResponse.model_validate(currency)


@router.get(
    "/config/list",
    summary="Get currency configuration",
    description="Returns the full currency configuration from YAML"
)
async def get_currency_config():
    """Retorna configuração completa de moedas"""
    config = get_currency_config()
    return {
        "base_currency": config.base_currency,
        "currencies": config.currencies,
        "collection": config.collection_config,
        "validation": config.validation_config,
        "storage": config.storage_config
    }


@router.get(
    "/config/{code}",
    summary="Get specific currency config",
    description="Returns configuration for a specific currency"
)
async def get_currency_config_by_code(code: str):
    """Busca config de uma moeda específica"""
    config = get_currency_config()
    currency = config.get_currency(code)

    if not currency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Currency {code} not configured"
        )

    return currency


@router.get(
    "/sources",
    response_model=List[DataSourceResponse],
    summary="List data sources",
    description="Returns all configured data sources"
)
async def list_sources(
    active_only: bool = Query(default=True),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Lista fontes de dados"""
    if active_only:
        sources = await repo.get_active_sources()
    else:
        # Precisaria de método para listar todas
        sources = await repo.get_active_sources()

    return [DataSourceResponse.model_validate(s) for s in sources]


@router.get(
    "/sources/{name}",
    response_model=DataSourceResponse,
    summary="Get data source details",
    description="Returns details for a specific data source"
)
async def get_source(
    name: str,
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca detalhes de uma fonte"""
    source = await repo.get_source(name)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {name} not found"
        )

    return DataSourceResponse.model_validate(source)