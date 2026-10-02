# Chem Process Studio - Database Design Plan

## Overview

This document outlines the proposed database architecture for Chem Process Studio, transitioning from the current file-based/local-storage approach to a production-ready multi-database system.

---

## Current State Analysis

| Component | Current Storage | Limitations |
|-----------|----------------|-------------|
| Vector embeddings | Chroma (`database/chroma/`) | No multi-tenancy, no metadata querying beyond filter |
| Keyword index | JSON file (`database/bm25_index.json`) | Single-file, not concurrent-safe, no scaling |
| PDF files | Filesystem (`database/uploads/`) | No metadata, versioning, access control |
| Workflow state | In-memory (ReactionState) | Lost on restart, no history, no resume |
| Predictions | Returned in API response only | No history, no analytics, no user association |
| Human reviews | In-memory only | Lost on restart, no audit trail |

---

## Proposed Database Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL (Primary)          │  Chroma (Vectors)              │
│  ┌─────────────────────────┐   │  ┌─────────────────────────┐   │
│  │ Users & Auth            │   │  │ Document Chunks         │   │
│  │ Workflows & Runs        │   │  │ Embeddings (bge-small)  │   │
│  │ Documents & Metadata    │   │  │ Metadata (doc_id, page) │   │
│  │ Predictions & Results   │   │  └─────────────────────────┘   │
│  │ Human Reviews           │                                    │
│  │ Audit Logs              │   │  Elasticsearch/OpenSearch      │
│  └─────────────────────────┘   │  (Future: BM25 replacement)    │
│                                │  ┌─────────────────────────┐   │
│  Redis (Cache/Queue)           │  │ Sparse Vectors / BM25   │   │
│  ┌─────────────────────────┐   │  │ Full-text Search        │   │
│  │ Session Cache           │   │  │ Analytics Queries       │   │
│  │ Rate Limiting           │   │  └─────────────────────────┘   │
│  │ Task Queue (Celery)     │                                    │
│  │ Pub/Sub (WebSockets)    │                                    │
│  └─────────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. PostgreSQL Schema (Primary Relational DB)

### Core Tables

```sql
-- Users & Authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    api_key_hash VARCHAR(64) UNIQUE,  -- For API access
    full_name VARCHAR(255),
    organization VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',  -- user, admin, service
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- API Keys (for programmatic access)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255),
    scopes JSONB DEFAULT '["predict"]',
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    revoked_at TIMESTAMPTZ
);

-- Documents (User-uploaded PDFs)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    document_id VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 checksum
    filename VARCHAR(512) NOT NULL,
    original_path VARCHAR(1024),
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    total_pages INT,
    chunk_count INT DEFAULT 0,
    chroma_collection VARCHAR(255),
    bm25_indexed BOOLEAN DEFAULT false,
    ingestion_status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    ingestion_error TEXT,
    checksum_sha256 VARCHAR(64) NOT NULL,
    metadata JSONB DEFAULT '{}',  -- Custom user metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- Document Chunks (Link to Chroma/Elasticsearch)
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id VARCHAR(64) UNIQUE NOT NULL,  -- Same as Chroma ID
    page_number INT NOT NULL,
    chunk_index INT NOT NULL,
    section_heading VARCHAR(512),
    char_start INT,
    char_end INT,
    token_count INT,
    chroma_indexed BOOLEAN DEFAULT false,
    bm25_indexed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Workflow Runs (Persisted ReactionState)
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(64),  -- For grouping related runs
    task_type VARCHAR(50) NOT NULL,  -- prediction, validation, explanation
    status VARCHAR(50) NOT NULL,  -- initialized, validated, retrieved, predicted, verified, retrying, human_review, completed, failed
    current_agent VARCHAR(50),
    
    -- Input
    smiles TEXT NOT NULL,
    canonical_smiles TEXT,
    conditions JSONB DEFAULT '{}',
    mechanism VARCHAR(255),
    user_query TEXT,
    
    -- Document references
    document_ids UUID[] DEFAULT '{}',  -- References to documents table
    
    -- Outputs (JSONB for flexibility)
    retrieved_context JSONB DEFAULT '[]',
    prediction TEXT,
    confidence DOUBLE PRECISION,
    prediction_mechanism TEXT,
    prediction_metadata JSONB DEFAULT '{}',
    validation_results JSONB DEFAULT '{}',
    validation_scores JSONB DEFAULT '{}',
    explanation_report TEXT,
    warnings JSONB DEFAULT '[]',
    
    -- Retry tracking
    retry_count JSONB DEFAULT '{"predictor": 0, "retriever": 0, "verifier": 0, "workflow": 0}',
    
    -- Human review
    human_feedback JSONB,
    
    -- Timing
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Workflow Steps (For debugging/resume)
CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_number INT NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,  -- pending, running, completed, failed, skipped
    input_state JSONB,
    output_state JSONB,
    error_message TEXT,
    middleware_results JSONB DEFAULT '[]',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INT
);

-- Human Reviews
CREATE TABLE human_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID REFERENCES workflow_runs(id) ON DELETE CASCADE,
    reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
    mode VARCHAR(50) NOT NULL,  -- pre_prediction, post_prediction
    decision VARCHAR(50) NOT NULL,  -- approve, reject, retry, modify
    comment TEXT,
    edited_fields JSONB DEFAULT '{}',
    payload_snapshot JSONB NOT NULL,  -- State at time of review
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

-- Audit Log (Immutable)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    workflow_run_id UUID REFERENCES workflow_runs(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,  -- predict, upload_document, review, etc.
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX idx_workflow_runs_user_status ON workflow_runs(user_id, status);
CREATE INDEX idx_workflow_runs_session ON workflow_runs(session_id);
CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_checksum ON documents(checksum_sha256);
CREATE INDEX idx_document_chunks_doc ON document_chunks(document_id);
CREATE INDEX idx_workflow_steps_run ON workflow_steps(workflow_run_id);
CREATE INDEX idx_human_reviews_run ON human_reviews(workflow_run_id);
CREATE INDEX idx_audit_logs_user_time ON audit_logs(user_id, created_at DESC);
```

---

## 2. Chroma (Vector Store) - Keep As-Is with Enhancements

**Current:** Single collection `chemistry_literature_bge_small`

**Enhanced Design:**
```python
# Multi-tenant collections
collections = {
    "global": "chemistry_literature_global",           # Public literature
    "user_{user_id}": f"chemistry_literature_user_{user_id}",  # Private docs
    "shared_{org_id}": f"chemistry_literature_org_{org_id}"    # Org-shared
}

# Metadata schema (already good, just ensure):
{
    "document_id": "uuid",           # FK to documents table
    "chunk_id": "sha256",            # Stable chunk ID
    "pdf_name": "string",
    "page": "int",
    "section_heading": "string",
    "chunk_index": "int",
    "embedding_model": "string",
    "content_hash": "sha256",
    "user_id": "uuid",               # For access control
    "organization_id": "uuid",       # Optional org sharing
    "visibility": "private|org|public"
}
```

---

## 3. Redis (Cache & Queue)

```python
# Session cache (TTL: 24h)
session:{session_id} -> {
    "user_id": "uuid",
    "workflow_run_id": "uuid",
    "state": {...},  # Partial ReactionState for resume
    "expires_at": "timestamp"
}

# Rate limiting
ratelimit:{user_id}:{endpoint} -> count (TTL: 1min)

# Task queue (Celery)
celery:queue:predictions -> [task_id, ...]
celery:queue:ingestion -> [task_id, ...]

# Pub/Sub for real-time updates
channel:workflow:{workflow_run_id} -> {step, status, progress}
channel:user:{user_id}:notifications -> {type, message}
```

---

## 4. Elasticsearch/OpenSearch (Future BM25 Replacement)

When BM25 JSON file becomes a bottleneck:
```json
{
  "mappings": {
    "properties": {
      "chunk_id": { "type": "keyword" },
      "content": { "type": "text", "analyzer": "chemistry_analyzer" },
      "document_id": { "type": "keyword" },
      "user_id": { "type": "keyword" },
      "page": { "type": "integer" },
      "section_heading": { "type": "text" },
      "pdf_name": { "type": "keyword" }
    }
  }
}
```

---

## Data Flow Mapping

| Operation | PostgreSQL | Chroma | Redis | Elasticsearch |
|-----------|-----------|--------|-------|---------------|
| User registers | ✅ Insert user | | | |
| API key created | ✅ Insert api_key | | | |
| PDF uploaded | ✅ Insert document (pending) | | ✅ Queue ingestion task | |
| PDF ingested | ✅ Update document + chunks | ✅ Add vectors | ✅ Update session | ✅ Index chunks |
| Prediction request | ✅ Create workflow_run | ✅ Query (filter by doc_ids) | ✅ Cache session | ✅ Query (filter by doc_ids) |
| Workflow step | ✅ Insert workflow_step | | ✅ Update session | |
| Retry | ✅ Update workflow_run | | | |
| Human review | ✅ Insert human_review | | ✅ Notify via pub/sub | |
| Prediction complete | ✅ Update workflow_run | | ✅ Invalidate cache | |
| Get history | ✅ Query workflow_runs | | | |

---

## Technology Recommendations

| Need | Recommended | Rationale |
|------|-------------|-----------|
| **Primary DB** | PostgreSQL 15+ | ACID, JSONB, arrays, UUID, mature, free |
| **Vector Search** | Chroma (dev) → pgvector or Pinecone (prod) | Chroma good for dev; pgvector keeps single DB; Pinecone for scale |
| **Keyword Search** | BM25 JSON (dev) → Elasticsearch (prod) | JSON file doesn't scale; ES is industry standard |
| **Cache/Queue** | Redis 7+ | Fast, supports streams, pub/sub, TTL |
| **Async Tasks** | Celery + Redis | Standard Python async, retries, monitoring |
| **Migrations** | Alembic | Version control for schema |

---

## Migration Strategy

### Phase 1: Foundation (Week 1-2)
1. Add PostgreSQL + Alembic to project
2. Create schema above
3. Add `User` model, authentication (JWT/API keys)
4. Wire `documents` table to PDF ingestion

### Phase 2: Workflow Persistence (Week 2-3)
1. Persist `workflow_runs` on every supervisor step
2. Add resume capability (load from DB on retry)
3. Add `workflow_steps` for debugging

### Phase 3: Multi-tenancy (Week 3-4)
1. User isolation in Chroma (collections per user)
2. Document ownership + sharing
3. API key authentication on `/predict`

### Phase 4: Observability (Week 4+)
1. Audit logging on all mutations
2. Human review persistence
3. Analytics queries (success rates, latency, etc.)

---

## Clarifying Questions Before Implementation

1. **Authentication**: Do you want JWT tokens, API keys, or both? Any OAuth providers (Google, GitHub)?

2. **Multi-tenancy Model**: 
   - Single-user (personal tool) → simpler, shared Chroma collection
   - Multi-user SaaS → per-user collections, strict isolation
   - Organization-based → shared collections per org

3. **Deployment Target**: 
   - Local dev only → SQLite + Chroma + JSON BM25 fine
   - Docker Compose → PostgreSQL + Redis + Chroma containers
   - Cloud (AWS/GCP/Azure) → Managed services (RDS, ElastiCache, Pinecone, OpenSearch)

4. **Scale Expectations**:
   - <100 predictions/day → Single PostgreSQL + Chroma fine
   - 1000+/day → Consider read replicas, connection pooling (PgBouncer)
   - 10000+/day → Separate vector DB, Elasticsearch cluster

5. **Existing Infrastructure**: Any preference for managed services (Supabase, Neon, Railway, etc.)?

6. **Human Review UI**: Will reviewers be internal team or external users? Affects auth model.

---

## Minimal Viable Schema (If Starting Small)

If you want to start with just **PostgreSQL + Chroma** (no Redis/Elasticsearch yet):

```sql
-- Just these 3 tables to start:
1. users + api_keys (auth)
2. documents (PDF metadata + chunk tracking)  
3. workflow_runs (full ReactionState as JSONB)
```

This gives you: user isolation, document management, prediction history, and resume capability without over-engineering.

---

*Last Updated: September 26, 2026*