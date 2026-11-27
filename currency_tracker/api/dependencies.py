# ============================================
# CurrencyTracker - API Dependencies
# ============================================

from functools import lru_cache
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.influxdb_client import InfluxDBClient
from currency_tracker.config.settings import get_settings

# Instâncias globais (singleton)
_rate_repo: RateRepository = None
_influxdb: InfluxDBClient = None

security = HTTPBearer(auto_error=False)


async def get_rate_repo() -> RateRepository:
    """Dependency para RateRepository"""
    global _rate_repo

    if _rate_repo is None:
        _rate_repo = RateRepository()
        await _rate_repo.initialize()

    return _rate_repo


async def get_influxdb() -> InfluxDBClient:
    """Dependency para InfluxDBClient"""
    global _influxdb

    if _influxdb is None:
        _influxdb = InfluxDBClient()
        await _influxdb.connect()

    return _influxdb


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Dependency para autenticação (placeholder)"""
    # TODO: Implementar JWT validation
    if credentials is None:
        # Para desenvolvimento, permite acesso sem auth
        return {"user_id": "anonymous", "roles": ["user"]}

    # Validar token JWT
    # payload = decode_jwt(credentials.credentials)
    # return payload

    return {"user_id": "anonymous", "roles": ["user"]}


def require_roles(*required_roles: str):
    """Dependency factory para roles obrigatórias"""
    async def _require_roles(user: dict = Depends(get_current_user)):
        user_roles = user.get("roles", [])
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Required roles: {required_roles}"
            )
        return user
    return _require_roles


# Cleanup functions
async def close_connections():
    """Fecha todas as conexões"""
    global _rate_repo, _influxdb

    if _rate_repo:
        await _rate_repo.close()
        _rate_repo = None

    if _influxdb:
        await _influxdb.close()
        _influxdb = None