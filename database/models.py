from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, BigInteger, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, desc, text
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    organization: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="user"
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="user")
    reviews: Mapped[list["HumanReview"]] = relationship(back_populates="reviewer")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    __table_args__ = (
        CheckConstraint("role IN ('user','admin','service')", name="users_role_check"),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    expires_at: Mapped[Optional[datetime]]
    last_used_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    revoked_at: Mapped[Optional[datetime]]

    user: Mapped["User"] = relationship(back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_user_id", "user_id"),
        Index("ix_api_keys_key_prefix", "key_prefix"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    total_pages: Mapped[Optional[int]]
    chunk_count: Mapped[int] = mapped_column(nullable=False, default=0)
    ingestion_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    ingestion_error: Mapped[Optional[str]] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    chroma_collection: Mapped[Optional[str]] = mapped_column(String(255))
    bm25_indexed: Mapped[bool] = mapped_column(nullable=False, default=False)
    document_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    deleted_at: Mapped[Optional[datetime]]

    user: Mapped["User"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    run_documents: Mapped[list["WorkflowRunDocument"]] = relationship(back_populates="document")

    __table_args__ = (
        CheckConstraint("ingestion_status IN ('pending','processing','completed','failed')", name="documents_ingestion_status_check"),
        CheckConstraint("file_size_bytes >= 0", name="documents_file_size_check"),
        CheckConstraint("total_pages >= 0", name="documents_total_pages_check"),
        CheckConstraint("chunk_count >= 0", name="documents_chunk_count_check"),
        Index("idx_documents_user", "user_id", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_documents_checksum", "checksum_sha256"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    page_number: Mapped[int] = mapped_column(nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    section_heading: Mapped[Optional[str]] = mapped_column(String(512))
    char_start: Mapped[Optional[int]]
    char_end: Mapped[Optional[int]]
    token_count: Mapped[Optional[int]]
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    chroma_indexed: Mapped[bool] = mapped_column(nullable=False, default=False)
    bm25_indexed: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        CheckConstraint("page_number > 0", name="chunks_page_number_check"),
        CheckConstraint("chunk_index >= 0", name="chunks_chunk_index_check"),
        CheckConstraint("char_start >= 0", name="chunks_char_start_check"),
        CheckConstraint("char_end >= char_start", name="chunks_char_end_check"),
        CheckConstraint("token_count >= 0", name="chunks_token_count_check"),
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_chunk_index"),
        Index("idx_chunks_document", "document_id"),
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(64))
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="initialized")
    current_agent: Mapped[Optional[str]] = mapped_column(String(50))
    current_step: Mapped[Optional[int]]
    smiles: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_smiles: Mapped[Optional[str]] = mapped_column(Text)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mechanism: Mapped[Optional[str]] = mapped_column(String(255))
    user_query: Mapped[Optional[str]] = mapped_column(Text)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    user: Mapped[Optional["User"]] = relationship(back_populates="workflow_runs")
    run_documents: Mapped[list["WorkflowRunDocument"]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")
    steps: Mapped[list["WorkflowStep"]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")
    reviews: Mapped[list["HumanReview"]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="workflow_run")

    __table_args__ = (
        CheckConstraint("task_type IN ('prediction','validation','explanation')", name="runs_task_type_check"),
        CheckConstraint("status IN ('initialized','running','human_review','completed','failed','cancelled')", name="runs_status_check"),
        Index("idx_runs_user_history", "user_id", desc("created_at")),
        Index("idx_runs_session", "session_id"),
    )


class WorkflowRunDocument(Base):
    __tablename__ = "workflow_run_documents"

    workflow_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="selected")
    retrieval_score: Mapped[Optional[float]]

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="run_documents")
    document: Mapped["Document"] = relationship(back_populates="run_documents")

    __table_args__ = (
        CheckConstraint("role IN ('selected','retrieved','citation')", name="run_docs_role_check"),
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(nullable=False)
    attempt_no: Mapped[int] = mapped_column(nullable=False, default=1)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_state: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_state: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    middleware_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    started_at: Mapped[Optional[datetime]]
    completed_at: Mapped[Optional[datetime]]
    duration_ms: Mapped[Optional[int]]

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="steps")

    __table_args__ = (
        CheckConstraint("step_number >= 0", name="steps_step_number_check"),
        CheckConstraint("attempt_no > 0", name="steps_attempt_no_check"),
        CheckConstraint("status IN ('pending','running','completed','failed','skipped')", name="steps_status_check"),
        CheckConstraint("duration_ms >= 0", name="steps_duration_check"),
        UniqueConstraint("workflow_run_id", "step_number", "attempt_no", name="uq_steps_run_step_attempt"),
        Index("idx_steps_run", "workflow_run_id", "step_number"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(nullable=False, default=1)
    prediction: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]]
    prediction_mechanism: Mapped[Optional[str]] = mapped_column(Text)
    prediction_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    validation_results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    validation_score: Mapped[Optional[float]]
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_name: Mapped[Optional[str]] = mapped_column(String(255))
    model_version: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]]

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="predictions")
    reviews: Mapped[list["HumanReview"]] = relationship(back_populates="prediction")

    __table_args__ = (
        CheckConstraint("attempt_no > 0", name="predictions_attempt_no_check"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="predictions_confidence_check"),
        CheckConstraint("validation_score BETWEEN 0 AND 1", name="predictions_validation_score_check"),
        UniqueConstraint("workflow_run_id", "attempt_no", name="uq_predictions_run_attempt"),
        Index("idx_predictions_run", "workflow_run_id", desc("created_at")),
    )


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    prediction_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="SET NULL")
    )
    reviewer_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    edited_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    payload_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]]

    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="reviews")
    prediction: Mapped[Optional["Prediction"]] = relationship(back_populates="reviews")
    reviewer: Mapped[Optional["User"]] = relationship(back_populates="reviews")

    __table_args__ = (
        CheckConstraint("mode IN ('pre_prediction','post_prediction')", name="reviews_mode_check"),
        CheckConstraint("decision IN ('approve','reject','retry','modify')", name="reviews_decision_check"),
        Index("idx_reviews_run", "workflow_run_id", desc("created_at")),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    workflow_run_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
    workflow_run: Mapped[Optional["WorkflowRun"]] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_user_time", "user_id", desc("created_at")),
    )