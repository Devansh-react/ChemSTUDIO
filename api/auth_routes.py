"""
Authentication Routes: Register, Login, Logout, API Key Management
"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from database.database import Database
from database.models import User, ApiKey
from database.service import DatabaseService
from api.auth import hash_api_key, get_current_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response Models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)
    organization: str | None = Field(None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default=["predict"])
    expires_in_days: int | None = Field(None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    api_key: str  # Only returned once!
    key_prefix: str
    name: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    organization: str | None
    role: str
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    user: UserResponse
    api_key: ApiKeyResponse


# Password hashing
def hash_password(password: str) -> str:
    """Hash password using SHA256 with salt (use bcrypt in production)."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{pwd_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, pwd_hash = stored_hash.split(":")
        return hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash
    except ValueError:
        return False


def generate_api_key(prefix: str = "cs") -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns: (raw_key, key_prefix, key_hash)
    """
    random_part = secrets.token_urlsafe(24)  # ~192 bits entropy
    raw_key = f"{prefix}_{random_part}"
    key_prefix = f"{prefix}_{random_part[:8]}"
    key_hash = hash_api_key(raw_key)
    return raw_key, key_prefix, key_hash


async def get_db_service() -> DatabaseService:
    db = Database()
    db.initialize()
    return DatabaseService(db)


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db_service: DatabaseService = Depends(get_db_service)):
    """
    Register a new user and generate their first API key.
    """
    # Check if user already exists
    existing = await db_service.get_user_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Hash password
    password_hash = hash_password(request.password)

    # Create user
    user = await db_service.create_user(
        email=request.email,
        hashed_password=password_hash,
        full_name=request.full_name or " ",
        organization=request.organization or " ",
        role="user",
    )

    # Generate API key
    raw_key, key_prefix, key_hash = generate_api_key()
    api_key = await db_service.create_api_key(
        user_id=user.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="Default API Key",
        scopes=request.scopes if hasattr(request, 'scopes') else ["predict"],
    )

    return LoginResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            organization=user.organization,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        api_key=ApiKeyResponse(
            api_key=raw_key,
            key_prefix=api_key.key_prefix,
            name=api_key.name,
            scopes=api_key.scopes,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
        )
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db_service: DatabaseService = Depends(get_db_service)):
    """
    Login with email/password, returns a new API key.
    """
    user = await db_service.get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    if not verify_password(request.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Generate new API key for this session
    raw_key, key_prefix, key_hash = generate_api_key()
    api_key = await db_service.create_api_key(
        user_id=user.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=f"Session key - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        scopes=["predict", "validate", "explain"],
    )

    return LoginResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            organization=user.organization,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        api_key=ApiKeyResponse(
            api_key=raw_key,
            key_prefix=api_key.key_prefix,
            name=api_key.name,
            scopes=api_key.scopes,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
        )
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_db_service),
):
    """
    Logout: revoke all API keys for the current user (or just the current one).
    For simplicity, we revoke all keys. In production, track which key was used.
    """
    # Get all API keys for user and revoke them
    async with db_service.db.session() as session:
        from sqlalchemy import update
        await session.execute(
            update(ApiKey)
            .where(ApiKey.user_id == current_user.id)
            .where(ApiKey.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await session.commit()

    return {"message": "Logged out successfully. All API keys revoked."}


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    request: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_db_service),
):
    """
    Create a new API key for the authenticated user.
    """
    raw_key, key_prefix, key_hash = generate_api_key("cs")
    
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    api_key = await db_service.create_api_key(
        user_id=current_user.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=request.name or " ",
        scopes=request.scopes or [],
        expires_at=expires_at or None,
    )

    return ApiKeyResponse(
        api_key=raw_key,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_db_service),
):
    """
    List all API keys for the current user (without the raw key).
    """
    async with db_service.db.session() as session:
        result = await session.execute(
            select(ApiKey)
            .where(ApiKey.user_id == current_user.id)
            .order_by(ApiKey.created_at.desc())
        )
        keys = result.scalars().all()

    return [
        ApiKeyResponse(
            api_key="***hidden***",  # Never return raw key again
            key_prefix=k.key_prefix,
            name=k.name,
            scopes=k.scopes,
            expires_at=k.expires_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_prefix}")
async def revoke_api_key(
    key_prefix: str,
    current_user: User = Depends(get_current_user),
    db_service: DatabaseService = Depends(get_db_service),
):
    """
    Revoke a specific API key by its prefix.
    """
    async with db_service.db.session() as session:
        from sqlalchemy import update
        result = await session.execute(
            update(ApiKey)
            .where(ApiKey.user_id == current_user.id)
            .where(ApiKey.key_prefix == key_prefix)
            .where(ApiKey.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await session.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found or already revoked"
            )

    return {"message": f"API key {key_prefix} revoked"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        organization=current_user.organization,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )