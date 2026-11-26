from functools import lru_cache
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from currency_tracker.storage.repository import RateRepository
from currency_tracker.config.settings import get_settings
_rate_repo: RateRepository = None
security = HTTPBearer(auto_error=False)

async def get_rate_repo() -> RateRepository:
    global _rate_repo
    if _rate_repo is None:
        _rate_repo = RateRepository()
        await _rate_repo.initialize()
    return _rate_repo

async def get_current_user(credentials: HTTPAuthorizationCredentials=Depends(security)) -> dict:
    if credentials is None:
        return {'user_id': 'anonymous', 'roles': ['user']}
    return {'user_id': 'anonymous', 'roles': ['user']}

def require_roles(*required_roles: str):

    async def _require_roles(user: dict=Depends(get_current_user)):
        user_roles = user.get('roles', [])
        if not any((role in user_roles for role in required_roles)):
            raise HTTPException(status_code=403, detail=f'Required roles: {required_roles}')
        return user
    return _require_roles

async def close_connections():
    global _rate_repo
    if _rate_repo:
        await _rate_repo.close()
        _rate_repo = None
