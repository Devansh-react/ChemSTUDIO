
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from database.database import Database, get_database
from database.models import ApiKey, User
from database.service import DatabaseService

#  secutiry schema : X-APi header 
api_key_header =APIKeyHeader(name="X-API-Key", auto_error=False)

def hash_api_key(raw_key:str):
    import hashlib
    return hashlib.sha256(raw_key.encode()).hexdigest()

def get_db_service()->DatabaseService:
    db = get_database()
    return DatabaseService(db)

async def get_api_key_record(
    api_key: str = Security(api_key_header),
    db_service: DatabaseService = Depends(get_db_service),
) -> ApiKey:
    if not  api_key:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="API key missing",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    key_hash = hash_api_key(api_key)
    api_key_record =await db_service.get_api_key_by_hash(key_hash)
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if api_key_record.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key revoked",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    from datetime import datetime, timezone
    if api_key_record.expires_at is not None and api_key_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key expired",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    # Update last_used_at (async, fire-and-forget)
    # We don't await to avoid adding latency to the request

    import asyncio
    asyncio.create_task(db_service.update_api_key_last_used(api_key_record.id))
    
    return api_key_record

async def get_current_user(
    api_key_record: ApiKey = Depends(get_api_key_record),
    db_service: DatabaseService = Depends(get_db_service),
) -> User:
    """
    Get the User associated with the validated API key.
    """
    user = await db_service.get_user_by_id(api_key_record.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user

def require_scope(required_scope: str):
    """
    Dependency factory: creates a dependency that checks if the API key has the required scope.
    Usage: _: None = Depends(require_scope("predict"))
    """
    async def scope_checker(api_key_record: ApiKey = Depends(get_api_key_record)) -> None:
        scopes = api_key_record.scopes or []
        if required_scope not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: '{required_scope}'",
            )
    return scope_checker

# Convenience dependencies for common scopes
require_predict_scope = require_scope("predict")
require_validate_scope = require_scope("validate")
require_explain_scope = require_scope("explain")
require_documents_read_scope = require_scope("documents:read")
require_documents_write_scope = require_scope("documents:write")
require_reviews_read_scope = require_scope("reviews:read")
require_reviews_write_scope = require_scope("reviews:write")