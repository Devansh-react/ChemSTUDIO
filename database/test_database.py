import asyncio
import os
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

# Set Windows event loop policy for psycopg3 async support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import Database, get_database, init_db, close_db, Base
from Config.settings import Settings


def ensure_test_database(test_url: str) -> None:
    db_url = make_url(test_url)
    database_name = db_url.database
    if not database_name:
        return

    admin_url = db_url.set(database="postgres")
    admin_engine = create_engine(admin_url.render_as_string(hide_password=False))
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            ).scalar()
            if exists is None:
                conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin_engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_db():
    test_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://chemstudio:chemstudio_dev@localhost:5432/chem_process_studio_test",
    )
    ensure_test_database(test_url)

    db = Database(test_url)
    db.initialize()

    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield db

    await db.close()


@pytest_asyncio.fixture
async def session(test_db: Database) -> AsyncGenerator[AsyncSession, None]:
    async with test_db.session() as session:
        yield session


@pytest.mark.asyncio
async def test_database_connection(test_db: Database):
    async with test_db.session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_create_user(session: AsyncSession):
    from sqlalchemy import insert
    from database.models import User

    user_data = {
        "email": "test@example.com",
        "hashed_password": "hashed_password_123",
        "full_name": "Test User",
        "organization": "Test Org",
        "role": "user",
    }
    stmt = insert(User).values(**user_data).returning(User.id)
    result = await session.execute(stmt)
    user_id = result.scalar()
    assert user_id is not None


@pytest.mark.asyncio
async def test_create_api_key(session: AsyncSession):
    from sqlalchemy import insert, select
    from database.models import User, ApiKey

    user_result = await session.execute(
        insert(User).values(email="apikey@test.com", hashed_password="pwd").returning(User.id)
    )
    user_id = user_result.scalar()

    api_key_data = {
        "user_id": user_id,
        "key_prefix": "cs_test",
        "key_hash": "hashed_key_123",
        "name": "Test API Key",
        "scopes": ["predict", "validate"],
    }
    stmt = insert(ApiKey).values(**api_key_data).returning(ApiKey.id)
    result = await session.execute(stmt)
    api_key_id = result.scalar()
    assert api_key_id is not None


@pytest.mark.asyncio
async def test_create_document(session: AsyncSession):
    from sqlalchemy import insert, select
    from database.models import User, Document

    user_result = await session.execute(
        insert(User).values(email="doc@test.com", hashed_password="pwd").returning(User.id)
    )
    user_id = user_result.scalar()

    doc_data = {
        "user_id": user_id,
        "filename": "test.pdf",
        "object_key": "uploads/test.pdf",
        "file_size_bytes": 1024,
        "mime_type": "application/pdf",
        "total_pages": 5,
        "checksum_sha256": "a" * 64,
    }
    stmt = insert(Document).values(**doc_data).returning(Document.id)
    result = await session.execute(stmt)
    doc_id = result.scalar()
    assert doc_id is not None


@pytest.mark.asyncio
async def test_workflow_run_crud(session: AsyncSession):
    from sqlalchemy import insert, select, update
    from database.models import User, WorkflowRun

    user_result = await session.execute(
        insert(User).values(email="workflow@test.com", hashed_password="pwd").returning(User.id)
    )
    user_id = user_result.scalar()

    run_data = {
        "user_id": user_id,
        "session_id": "session_123",
        "task_type": "prediction",
        "status": "initialized",
        "smiles": "CCO",
        "canonical_smiles": "CCO",
        "conditions": {"temperature": "25C", "solvent": "water"},
        "mechanism": "SN2",
        "user_query": "Predict reaction",
    }
    stmt = insert(WorkflowRun).values(**run_data).returning(WorkflowRun.id)
    result = await session.execute(stmt)
    run_id = result.scalar()
    assert run_id is not None

    result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    run = result.scalar_one()
    assert run.smiles == "CCO"
    assert run.status == "initialized"

    await session.execute(
        update(WorkflowRun).where(WorkflowRun.id == run_id).values(status="completed")
    )
    await session.commit()

    result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    run = result.scalar_one()
    assert run.status == "completed"


@pytest.mark.asyncio
async def test_predictions_and_reviews(session: AsyncSession):
    from sqlalchemy import insert, select
    from database.models import User, WorkflowRun, Prediction, HumanReview

    user_result = await session.execute(
        insert(User).values(email="pred@test.com", hashed_password="pwd").returning(User.id)
    )
    user_id = user_result.scalar()

    run_result = await session.execute(
        insert(WorkflowRun)
        .values(user_id=user_id, task_type="prediction", smiles="CCO", status="completed")
        .returning(WorkflowRun.id)
    )
    run_id = run_result.scalar()

    pred_data = {
        "workflow_run_id": run_id,
        "attempt_no": 1,
        "prediction": "CCO >> CCO",
        "confidence": 0.85,
        "prediction_mechanism": "SN2",
        "validation_score": 0.9,
        "model_name": "test_model",
        "model_version": "1.0",
    }
    stmt = insert(Prediction).values(**pred_data).returning(Prediction.id)
    result = await session.execute(stmt)
    pred_id = result.scalar()
    assert pred_id is not None

    review_data = {
        "workflow_run_id": run_id,
        "prediction_id": pred_id,
        "reviewer_id": user_id,
        "mode": "post_prediction",
        "decision": "approve",
        "comment": "Looks good",
        "edited_fields": {},
        "payload_snapshot": {"prediction": "CCO >> CCO"},
    }
    stmt = insert(HumanReview).values(**review_data).returning(HumanReview.id)
    result = await session.execute(stmt)
    review_id = result.scalar()
    assert review_id is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])