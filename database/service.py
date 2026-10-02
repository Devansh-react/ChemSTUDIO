from datetime import datetime
from uuid import UUID
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    User, ApiKey, Document, DocumentChunk,
    WorkflowRun, WorkflowStep, Prediction, HumanReview, WorkflowRunDocument
)
from database.database import Database


class DatabaseService:
    def __init__(self, db: Database):
        self.db = db

    # ============ USERS ============
    async def create_user(self, email: str, hashed_password: str, full_name: str = None,
                          organization: str = None, role: str = "user") -> User:
        async with self.db.session() as session:
            user = User(
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                organization=organization,
                role=role
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with self.db.session() as session:
            result = await session.execute(select(User).where(User.email == email))
            return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        async with self.db.session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    # ============ API KEYS ============
    async def create_api_key(self, user_id: UUID, key_prefix: str, key_hash: str,
                             name: str, scopes: List[str] = None, expires_at: datetime = None) -> ApiKey:
        async with self.db.session() as session:
            api_key = ApiKey(
                user_id=user_id,
                key_prefix=key_prefix,
                key_hash=key_hash,
                name=name,
                scopes=scopes or ["predict"],
                expires_at=expires_at
            )
            session.add(api_key)
            await session.commit()
            await session.refresh(api_key)
            return api_key

    async def get_api_key_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        async with self.db.session() as session:
            result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
            return result.scalar_one_or_none()

    async def update_api_key_last_used(self, api_key_id: UUID) -> None:
        async with self.db.session() as session:
            await session.execute(
                update(ApiKey).where(ApiKey.id == api_key_id).values(last_used_at=datetime.utcnow())
            )
            await session.commit()

    # ============ DOCUMENTS ============
    async def create_document(self, user_id: UUID, filename: str, object_key: str,
                              file_size_bytes: int, checksum_sha256: str,
                              mime_type: str = None, total_pages: int = None) -> Document:
        async with self.db.session() as session:
            doc = Document(
                user_id=user_id,
                filename=filename,
                object_key=object_key,
                file_size_bytes=file_size_bytes,
                checksum_sha256=checksum_sha256,
                mime_type=mime_type,
                total_pages=total_pages,
                ingestion_status="pending"
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
            return doc

    async def update_document_ingestion(self, doc_id: UUID, status: str,
                                        chunk_count: int = None, chroma_collection: str = None,
                                        error: str = None, bm25_indexed: bool = False) -> Document:
        async with self.db.session() as session:
            values = {"ingestion_status": status, "updated_at": datetime.utcnow()}
            if chunk_count is not None:
                values["chunk_count"] = chunk_count
            if chroma_collection:
                values["chroma_collection"] = chroma_collection
            if error:
                values["ingestion_error"] = error
            if bm25_indexed:
                values["bm25_indexed"] = True

            await session.execute(
                update(Document).where(Document.id == doc_id).values(**values)
            )
            await session.commit()
            return await self.get_document(doc_id)

    async def get_document(self, doc_id: UUID) -> Optional[Document]:
        async with self.db.session() as session:
            result = await session.execute(select(Document).where(Document.id == doc_id))
            return result.scalar_one_or_none()

    async def get_user_documents(self, user_id: UUID) -> List[Document]:
        async with self.db.session() as session:
            result = await session.execute(
                select(Document).where(Document.user_id == user_id, Document.deleted_at.is_(None))
                .order_by(Document.created_at.desc())
            )
            return result.scalars().all()

    async def create_document_chunks(self, doc_id: UUID, chunks: List[dict]) -> List[DocumentChunk]:
        async with self.db.session() as session:
            chunk_objects = [
                DocumentChunk(
                    document_id=doc_id,
                    chunk_id=c["chunk_id"],
                    page_number=c["page_number"],
                    chunk_index=c["chunk_index"],
                    section_heading=c.get("section_heading"),
                    char_start=c.get("char_start"),
                    char_end=c.get("char_end"),
                    token_count=c.get("token_count"),
                    content_hash=c.get("content_hash")
                )
                for c in chunks
            ]
            session.add_all(chunk_objects)
            await session.commit()
            for c in chunk_objects:
                await session.refresh(c)
            return chunk_objects

    # ============ WORKFLOW RUNS ============
    async def create_workflow_run(self, user_id: UUID, task_type: str, smiles: str,
                                  session_id: str = None, canonical_smiles: str = None,
                                  conditions: dict = None, mechanism: str = None,
                                  user_query: str = None) -> WorkflowRun:
        async with self.db.session() as session:
            run = WorkflowRun(
                user_id=user_id,
                task_type=task_type,
                status="initialized",
                smiles=smiles,
                canonical_smiles=canonical_smiles,
                conditions=conditions or {},
                mechanism=mechanism,
                user_query=user_query,
                session_id=session_id
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def update_workflow_run_status(self, run_id: UUID, status: str,
                                         current_agent: str = None,
                                         current_step: int = None) -> WorkflowRun:
        async with self.db.session() as session:
            values = {"status": status, "updated_at": datetime.utcnow()}
            if current_agent:
                values["current_agent"] = current_agent
            if current_step is not None:
                values["current_step"] = current_step
            if status == "completed":
                values["completed_at"] = datetime.utcnow()

            await session.execute(
                update(WorkflowRun).where(WorkflowRun.id == run_id).values(**values)
            )
            await session.commit()
            return await self.get_workflow_run(run_id)

    async def get_workflow_run(self, run_id: UUID) -> Optional[WorkflowRun]:
        async with self.db.session() as session:
            result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            return result.scalar_one_or_none()

    async def create_workflow_step(self, run_id: UUID, step_number: int, agent_name: str,
                                   attempt_no: int = 1, status: str = "pending",
                                   input_state: dict = None, output_state: dict = None) -> WorkflowStep:
        async with self.db.session() as session:
            step = WorkflowStep(
                workflow_run_id=run_id,
                step_number=step_number,
                attempt_no=attempt_no,
                agent_name=agent_name,
                status=status,
                input_state=input_state,
                output_state=output_state
            )
            session.add(step)
            await session.commit()
            await session.refresh(step)
            return step

    async def complete_workflow_step(self, step_id: UUID, status: str,
                                     output_state: dict = None, error: str = None,
                                     duration_ms: int = None) -> WorkflowStep:
        async with self.db.session() as session:
            values = {"status": status, "completed_at": datetime.utcnow()}
            if output_state:
                values["output_state"] = output_state
            if error:
                values["error_message"] = error
            if duration_ms:
                values["duration_ms"] = duration_ms

            await session.execute(
                update(WorkflowStep).where(WorkflowStep.id == step_id).values(**values)
            )
            await session.commit()
            return await self.get_workflow_step(step_id)

    async def get_workflow_step(self, step_id: UUID) -> Optional[WorkflowStep]:
        async with self.db.session() as session:
            result = await session.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
            return result.scalar_one_or_none()

    # ============ PREDICTIONS ============
    async def create_prediction(self, run_id: UUID, attempt_no: int, prediction: str,
                                confidence: float = None, mechanism: str = None,
                                metadata: dict = None, validation_results: dict = None,
                                validation_score: float = None, model_name: str = None,
                                model_version: str = None) -> Prediction:
        async with self.db.session() as session:
            pred = Prediction(
                workflow_run_id=run_id,
                attempt_no=attempt_no,
                prediction=prediction,
                confidence=confidence,
                prediction_mechanism=mechanism,
                prediction_metadata=metadata or {},
                validation_results=validation_results or {},
                validation_score=validation_score,
                model_name=model_name,
                model_version=model_version
            )
            session.add(pred)
            await session.commit()
            await session.refresh(pred)
            return pred

    # ============ HUMAN REVIEWS ============
    async def create_human_review(self, run_id: UUID, reviewer_id: UUID, mode: str,
                                  decision: str, prediction_id: UUID = None,
                                  comment: str = None, edited_fields: dict = None,
                                  payload_snapshot: dict = None) -> HumanReview:
        async with self.db.session() as session:
            review = HumanReview(
                workflow_run_id=run_id,
                prediction_id=prediction_id,
                reviewer_id=reviewer_id,
                mode=mode,
                decision=decision,
                comment=comment,
                edited_fields=edited_fields or {},
                payload_snapshot=payload_snapshot or {}
            )
            session.add(review)
            await session.commit()
            await session.refresh(review)
            return review