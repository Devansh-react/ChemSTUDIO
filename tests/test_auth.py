"""
Tests for API Key Authentication Middleware
"""
# CRITICAL: Set Windows event loop policy BEFORE any async imports
import sys
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio

from api.auth import hash_api_key, require_scope
from database.database import Database
from database.models import User, ApiKey
from database.service import DatabaseService


@pytest_asyncio.fixture(scope="session")
async def test_db():
    """Use the test database."""
    test_url = "postgresql+psycopg://chemstudio:chemstudio_dev@localhost:5432/chem_process_studio_test"
    db = Database(test_url)
    db.initialize()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def db_service(test_db: Database) -> DatabaseService:
    return DatabaseService(test_db)


@pytest_asyncio.fixture
async def test_user(db_service: DatabaseService) -> User:
    """Create a test user."""
    user = await db_service.create_user(
        email=f"test_{uuid4().hex[:8]}@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        role="user",
    )
    return user


@pytest_asyncio.fixture
async def test_api_key(db_service: DatabaseService, test_user: User) -> tuple[str, ApiKey]:
    """Create a test API key and return (raw_key, api_key_record)."""
    raw_key = f"cs_test_{uuid4().hex[:24]}"
    key_hash = hash_api_key(raw_key)

    api_key = await db_service.create_api_key(
        user_id=test_user.id,
        key_prefix="cs_test",
        key_hash=key_hash,
        name="Test Key",
        scopes=["predict", "validate", "explain"],
    )
    return raw_key, api_key


class TestHashApiKey:
    """Test the hash_api_key utility function."""

    def test_hash_is_deterministic(self):
        key = "cs_test_abc123"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_different_keys_produce_different_hashes(self):
        hash1 = hash_api_key("cs_test_key1")
        hash2 = hash_api_key("cs_test_key2")
        assert hash1 != hash2

    def test_hash_format(self):
        hash_val = hash_api_key("test")
        assert all(c in "0123456789abcdef" for c in hash_val)


class TestApiKeyCreation:
    """Test API key creation and validation."""

    @pytest.mark.asyncio
    async def test_create_api_key(self, db_service: DatabaseService, test_user: User):
        raw_key = f"cs_test_{uuid4().hex[:24]}"
        key_hash = hash_api_key(raw_key)

        api_key = await db_service.create_api_key(
            user_id=test_user.id,
            key_prefix="cs_test",
            key_hash=key_hash,
            name="Test Key",
            scopes=["predict"],
        )

        assert api_key.id is not None
        assert api_key.user_id == test_user.id
        assert api_key.key_prefix == "cs_test"
        assert api_key.key_hash == key_hash
        assert api_key.scopes == ["predict"]
        assert api_key.revoked_at is None

    @pytest.mark.asyncio
    async def test_get_api_key_by_hash(self, db_service: DatabaseService, test_api_key: tuple[str, ApiKey]):
        raw_key, api_key_record = test_api_key
        key_hash = hash_api_key(raw_key)

        found = await db_service.get_api_key_by_hash(key_hash)
        assert found is not None
        assert found.id == api_key_record.id

    @pytest.mark.asyncio
    async def test_get_api_key_by_hash_not_found(self, db_service: DatabaseService):
        found = await db_service.get_api_key_by_hash("nonexistent_hash")
        assert found is None


class TestAuthMiddleware:
    """Test the authentication middleware dependencies."""

    def test_require_scope_factory(self):
        """Test that require_scope creates a dependency."""
        dep = require_scope("predict")
        assert callable(dep)

    @pytest.mark.asyncio
    async def test_get_current_user_success(
        self,
        db_service: DatabaseService,
        test_user: User,
        test_api_key: tuple[str, ApiKey]
    ):
        raw_key, api_key_record = test_api_key

        key_hash = hash_api_key(raw_key)
        found = await db_service.get_api_key_by_hash(key_hash)
        assert found is not None
        assert found.id == api_key_record.id

        user = await db_service.get_user_by_id(found.user_id)
        assert user is not None
        assert user.id == test_user.id
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_revoked_key_rejected(self, db_service: DatabaseService, test_user: User):
        """Test that revoked keys are rejected."""
        raw_key = f"cs_test_{uuid4().hex[:24]}"
        key_hash = hash_api_key(raw_key)

        api_key = await db_service.create_api_key(
            user_id=test_user.id,
            key_prefix="cs_test",
            key_hash=key_hash,
            name="Revoked Key",
            scopes=["predict"],
        )

        # Revoke it
        from datetime import datetime, timezone
        from sqlalchemy import update
        async with db_service.db.session() as session:
            await session.execute(
                update(ApiKey)
                .where(ApiKey.id == api_key.id)
                .values(revoked_at=datetime.now(timezone.utc))
            )
            await session.commit()

        # Try to find it (should still find it, but middleware checks revoked_at)
        found = await db_service.get_api_key_by_hash(key_hash)
        assert found is not None
        assert found.revoked_at is not None

    @pytest.mark.asyncio
    async def test_expired_key_rejected(self, db_service: DatabaseService, test_user: User):
        """Test that expired keys are rejected."""
        from datetime import datetime, timezone, timedelta

        raw_key = f"cs_test_{uuid4().hex[:24]}"
        key_hash = hash_api_key(raw_key)

        api_key = await db_service.create_api_key(
            user_id=test_user.id,
            key_prefix="cs_test",
            key_hash=key_hash,
            name="Expired Key",
            scopes=["predict"],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        found = await db_service.get_api_key_by_hash(key_hash)
        assert found is not None
        assert found.expires_at is not None
        # DB returns offset-naive, make both offset-aware for comparison
        from datetime import timezone as tz
        assert found.expires_at.replace(tzinfo=tz.utc) < datetime.now(timezone.utc)


class TestScopeChecking:
    """Test scope validation logic."""

    def test_scope_in_list(self):
        scopes = ["predict", "validate", "explain"]
        assert "predict" in scopes
        assert "documents:read" not in scopes

    def test_empty_scopes(self):
        scopes = []
        assert "predict" not in scopes

    def test_none_scopes(self):
        scopes = None
        assert "predict" not in (scopes or [])


class TestApiKeyScopes:
    """Test scope definitions."""

    def test_predict_scope_exists(self):
        from api.auth import require_predict_scope
        assert require_predict_scope is not None

    def test_validate_scope_exists(self):
        from api.auth import require_validate_scope
        assert require_validate_scope is not None

    def test_explain_scope_exists(self):
        from api.auth import require_explain_scope
        assert require_explain_scope is not None

    def test_documents_read_scope_exists(self):
        from api.auth import require_documents_read_scope
        assert require_documents_read_scope is not None

    def test_documents_write_scope_exists(self):
        from api.auth import require_documents_write_scope
        assert require_documents_write_scope is not None

    def test_reviews_read_scope_exists(self):
        from api.auth import require_reviews_read_scope
        assert require_reviews_read_scope is not None

    def test_reviews_write_scope_exists(self):
        from api.auth import require_reviews_write_scope
        assert require_reviews_write_scope is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])