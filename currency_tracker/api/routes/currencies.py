from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from currency_tracker.api.schemas import CurrencyResponse, DataSourceResponse
from currency_tracker.config.settings import get_currency_config
router = APIRouter(prefix='/currencies', tags=['Currencies'])

@router.get('/', response_model=List[CurrencyResponse], summary='List all currencies')
async def list_currencies(active_only: bool=Query(default=True)):
    config = get_currency_config()
    currencies = config.currencies
    result = []
    for c in currencies:
        result.append(CurrencyResponse(id=len(result) + 1, uuid='test', code=c['code'], name=c['name'], symbol=c.get('symbol'), symbol_native=c.get('symbol_native'), decimal_places=c.get('decimal_places', 4), is_base=c.get('is_base', False), is_active=c.get('is_active', True), category=c.get('category'), priority=c.get('priority'), created_at='2024-01-01T00:00:00', updated_at='2024-01-01T00:00:00'))
    return result

@router.get('/{code}', response_model=CurrencyResponse, summary='Get currency details')
async def get_currency(code: str):
    config = get_currency_config()
    currency = config.get_currency(code)
    if not currency:
        raise HTTPException(status_code=404, detail=f'Currency {code} not found')
    return CurrencyResponse(id=1, uuid='test', code=currency['code'], name=currency['name'], symbol=currency.get('symbol'), symbol_native=currency.get('symbol_native'), decimal_places=currency.get('decimal_places', 4), is_base=currency.get('is_base', False), is_active=currency.get('is_active', True), category=currency.get('category'), priority=currency.get('priority'), created_at='2024-01-01T00:00:00', updated_at='2024-01-01T00:00:00')

@router.get('/config/list', summary='Get currency configuration')
async def get_currency_config():
    config = get_currency_config()
    return {'base_currency': config.base_currency, 'currencies': config.currencies, 'collection': config.collection_config, 'validation': config.validation_config, 'storage': config.storage_config}

@router.get('/config/{code}', summary='Get specific currency config')
async def get_currency_config_by_code(code: str):
    config = get_currency_config()
    currency = config.get_currency(code)
    if not currency:
        raise HTTPException(status_code=404, detail=f'Currency {code} not configured')
    return currency

@router.get('/sources', response_model=List[DataSourceResponse], summary='List data sources')
async def list_sources(active_only: bool=Query(default=True)):
    config = get_currency_config()
    sources = [{'name': 'awesomeapi', 'display_name': 'Awesome API', 'base_url': 'https://economia.awesomeapi.com.br', 'api_key_required': False, 'rate_limit_per_second': 10, 'priority': 1}]
    result = []
    for i, s in enumerate(sources):
        result.append(DataSourceResponse(id=i + 1, name=s['name'], display_name=s['display_name'], base_url=s['base_url'], api_key_required=s['api_key_required'], rate_limit_per_second=s['rate_limit_per_second'], is_active=s.get('is_active', True), priority=s['priority'], created_at='2024-01-01T00:00:00', updated_at='2024-01-01T00:00:00'))
    return result
