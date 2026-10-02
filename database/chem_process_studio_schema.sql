-- Chem Process Studio: PostgreSQL 15+ reference schema
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email varchar(255) NOT NULL UNIQUE,
  hashed_password varchar(255), full_name varchar(255), organization varchar(255),
  role varchar(50) NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin','service')),
  is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_prefix varchar(16) NOT NULL, key_hash varchar(255) NOT NULL UNIQUE, name varchar(255) NOT NULL,
  scopes jsonb NOT NULL DEFAULT '["predict"]', expires_at timestamptz, last_used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz
);
CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename varchar(512) NOT NULL, object_key varchar(1024) NOT NULL UNIQUE, file_size_bytes bigint CHECK (file_size_bytes >= 0),
  mime_type varchar(100), total_pages integer CHECK (total_pages >= 0), chunk_count integer NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
  ingestion_status varchar(20) NOT NULL DEFAULT 'pending' CHECK (ingestion_status IN ('pending','processing','completed','failed')),
  ingestion_error text, checksum_sha256 char(64) NOT NULL, chroma_collection varchar(255), bm25_indexed boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz
);
CREATE TABLE document_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_id varchar(128) NOT NULL UNIQUE, page_number integer NOT NULL CHECK (page_number > 0), chunk_index integer NOT NULL CHECK (chunk_index >= 0),
  section_heading varchar(512), char_start integer CHECK (char_start >= 0), char_end integer CHECK (char_end >= char_start), token_count integer CHECK (token_count >= 0),
  content_hash char(64), chroma_indexed boolean NOT NULL DEFAULT false, bm25_indexed boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);
CREATE TABLE workflow_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid REFERENCES users(id) ON DELETE SET NULL, session_id varchar(64),
  task_type varchar(50) NOT NULL CHECK (task_type IN ('prediction','validation','explanation')),
  status varchar(30) NOT NULL DEFAULT 'initialized' CHECK (status IN ('initialized','running','human_review','completed','failed','cancelled')),
  current_agent varchar(50), current_step integer, smiles text NOT NULL, canonical_smiles text, conditions jsonb NOT NULL DEFAULT '{}', mechanism varchar(255), user_query text,
  state_snapshot jsonb NOT NULL DEFAULT '{}', started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE workflow_run_documents (
  workflow_run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE, document_id uuid NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
  role varchar(20) NOT NULL DEFAULT 'selected' CHECK (role IN ('selected','retrieved','citation')), retrieval_score double precision,
  PRIMARY KEY (workflow_run_id, document_id)
);
CREATE TABLE workflow_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workflow_run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  step_number integer NOT NULL CHECK (step_number >= 0), attempt_no integer NOT NULL DEFAULT 1 CHECK (attempt_no > 0), agent_name varchar(50) NOT NULL,
  status varchar(20) NOT NULL CHECK (status IN ('pending','running','completed','failed','skipped')), input_state jsonb, output_state jsonb, error_message text,
  middleware_results jsonb NOT NULL DEFAULT '[]', started_at timestamptz, completed_at timestamptz, duration_ms integer CHECK (duration_ms >= 0),
  UNIQUE (workflow_run_id, step_number, attempt_no)
);
CREATE TABLE predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workflow_run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  attempt_no integer NOT NULL DEFAULT 1 CHECK (attempt_no > 0), prediction text NOT NULL, confidence double precision CHECK (confidence BETWEEN 0 AND 1),
  prediction_mechanism text, prediction_metadata jsonb NOT NULL DEFAULT '{}', validation_results jsonb NOT NULL DEFAULT '{}', validation_score double precision,
  warnings jsonb NOT NULL DEFAULT '[]', model_name varchar(255), model_version varchar(255), created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
  UNIQUE (workflow_run_id, attempt_no)
);
CREATE TABLE human_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workflow_run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
  prediction_id uuid REFERENCES predictions(id) ON DELETE SET NULL, reviewer_id uuid REFERENCES users(id) ON DELETE SET NULL,
  mode varchar(30) NOT NULL CHECK (mode IN ('pre_prediction','post_prediction')), decision varchar(20) NOT NULL CHECK (decision IN ('approve','reject','retry','modify')),
  comment text, edited_fields jsonb NOT NULL DEFAULT '{}', payload_snapshot jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), resolved_at timestamptz
);
CREATE TABLE audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid REFERENCES users(id) ON DELETE SET NULL, workflow_run_id uuid REFERENCES workflow_runs(id) ON DELETE SET NULL,
  action varchar(100) NOT NULL, resource_type varchar(50), resource_id uuid, details jsonb NOT NULL DEFAULT '{}', ip_address inet, user_agent text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_user ON documents(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_checksum ON documents(checksum_sha256);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_runs_user_history ON workflow_runs(user_id, created_at DESC);
CREATE INDEX idx_runs_session ON workflow_runs(session_id);
CREATE INDEX idx_steps_run ON workflow_steps(workflow_run_id, step_number);
CREATE INDEX idx_predictions_run ON predictions(workflow_run_id, created_at DESC);
CREATE INDEX idx_reviews_run ON human_reviews(workflow_run_id, created_at DESC);
CREATE INDEX idx_audit_user_time ON audit_logs(user_id, created_at DESC);
