

<div align="center">
  <img src="logo.png" alt="Chem Process Studio logo" width="80%" />
</div>

# ChenSTUDIO V2
### (Building a chemistry workflow with AI-assisted reaction prediction, retrieval, and explanation)
 
Chem Process Studio is an experimental AI-assisted chemistry workflow for reaction prediction, document-grounded retrieval, and explanation generation. The repository combines chemistry tooling, retrieval-augmented generation, and a supervisor-style orchestration layer around a shared workflow state.

> Status: the core multi-agent workflow and Retrieval V2 path are implemented. The `/predict` API currently accepts reaction data and optional PDF paths, ingests those PDFs, performs scoped hybrid retrieval, and returns prediction, explanation, verification, metadata, and warnings. The predictor/runtime integrations, production document lifecycle, and UI are still in progress.
>
> **Recent Fixes (Sept 2026):** Canonical SMILES reactant order bug fixed (preserves original order for prediction), LLM error handling with fallbacks, retry middleware refinements, intent classification parsing improved. See [UPGRADES_AND_ARCHITECTURE.md](UPGRADES_AND_ARCHITECTURE.md) for details.

Retrieval V2 is documented in [V2_retriever.md](V2_retriever.md), including its ingestion flow, dense plus BM25 search, reciprocal-rank fusion, cross-encoder reranking, traceability, improvements, and limitations.

---

## What this project is trying to do

The project aims to support a chemistry workflow where a user provides a reaction input such as a SMILES string and reaction conditions, and the system can:

- validate the input molecule,
- optionally retrieve supporting literature from uploaded PDFs,
- generate a predicted reaction outcome and mechanism,
- verify the output against chemistry rules and retrieved context,
- produce a readable explanation report,
- and optionally pause for human review when confidence or validation quality is low.

The repository is organized around a multi-agent pattern in which each agent handles one responsibility and a supervisor coordinates them.

---

## High-level pipeline

The current workflow is structured as follows:

1. User input is collected
   - The system expects a reaction input such as a SMILES string and a dictionary of reaction conditions.
   - The shared workflow state is defined in the schema layer and is passed between agents.

2. Supervisor plans the workflow
   - The supervisor agent inspects the requested intent and decides which agents need to run.
   - Supported intents include prediction, validation, and explanation.
   - The supervisor uses an agent registry to resolve which callable agent should run and what middleware should be applied.

3. Validator agent runs first for prediction workflows
   - The validator checks the input SMILES with RDKit.
   - It canonicalizes the molecule when possible and returns validation warnings/errors.
   - The resulting canonical SMILES is stored in the workflow state.

4. Retriever agent checks for supporting context
  - If PDFs were successfully ingested, the retriever builds one chemistry-aware query from the canonical SMILES, mechanism, and reaction conditions.
  - It searches Chroma dense embeddings and the persistent local BM25 index, combines rankings with reciprocal-rank fusion, and reranks the candidates with a cross-encoder.
  - Retrieval is scoped to the checksum-based document IDs uploaded for the request, and the final context keeps page citations and retrieval diagnostics.

5. Pre-review step can interrupt before prediction
   - A pre-review human review payload can be created before the predictor runs.
   - This allows the user to review the input payload and approve, modify, or reject it before prediction begins.

6. Predictor agent generates the reaction prediction
   - The predictor wraps the reaction prediction logic in a dedicated tool class.
   - It preprocesses the state, builds a prediction prompt, calls the prediction logic, and formats the result.
   - The output includes the predicted reaction, confidence score, mechanism, and metadata.

7. Verifier agent evaluates the predicted result
   - The verifier checks whether the predicted product is valid with RDKit.
   - It also scores how well the predicted mechanism and context align with the retrieved evidence.
   - The verification output is stored as validation results and validation scores.

8. Retry and human-review middleware can change the path
   - If validation fails, the supervisor may retry from the predictor or retriever stage.
   - If confidence is low or validation remains weak after retries, the workflow can trigger a human review step.

9. Explainer agent produces the final narrative report
   - The explainer takes the state and converts it into a concise human-readable report.
   - It does not invent new facts; it simply transforms the already-generated state into a clear summary.

---

## Supervisor agent overview

The supervisor is the orchestration layer of the project. Its responsibilities include:

- receiving the current workflow state and an intent,
- selecting the next agent to run based on the workflow plan,
- executing the agent call,
- applying any required middleware before and after the agent step,
- handling retry logic when validation fails,
- and triggering a human review path when the workflow requires human approval or correction.

The supervisor currently exposes the following logical operations:

- `plan(intent)`: chooses a staged workflow for prediction, validation, or explanation.
- `invoke(state, agent_name)`: resolves an agent from the registry and runs it with middleware.
- `execute_workflow(state, workflow)`: runs a sequence of agents in order.
- `handle_middleware(state, middleware_name, middleware_result)`: routes retry or review decisions.

In practice, the supervisor is the central coordinator that connects the validator, retriever, predictor, verifier, explainer, and human-review components.

---

## Main project structure

```text
Chem_Procress_studio/
├── agents/
│   ├── explainer.py          # Produces the final explanation report.
│   ├── predictor.py         # Calls the reaction prediction workflow.
│   ├── pre_review.py        # Pre-prediction human review wrapper.
│   ├── retriever.py        # Uses uploaded literature context for retrieval.
│   ├── supervisor.py       # Main orchestration layer.
│   ├── validator.py        # Validates and canonicalizes SMILES.
│   └── verifier.py         # Checks predictions against context/mechanism rules.
├── api/
│   └── main.py             # FastAPI application entrypoint and health route.
├── database/
│   ├── chroma/             # Chroma persistence directory.
│   └── postgress/          # PostgreSQL storage folder placeholder.
├── graph/
│   └── state.py            # Shared workflow state definition placeholder.
├── middleware/
│   ├── guardrails.py       # Guardrails scaffolding.
│   ├── interrupts.py       # Interrupt-related helpers.
│   ├── limits.py           # Tool/model rate-limit middleware.
│   ├── logging.py          # Logging scaffolding.
│   └── retry.py            # Retry decision middleware.
├── prompts/
│   ├── explainer_prompt.py
│   ├── prediction_prompt.py
│   ├── Retriever_prompt.py
│   ├── Validator_prompt.py
│   └── verifier_prompt.py
├── services/
│   └── pdf_inestion_services.py
├── skills/
│   ├── explain.md
│   ├── literature_search.md
│   ├── predict.md
│   ├── report.md
│   └── Validate.md
├── tools/
│   ├── chemistry/
│   │   └── RDKit_tool.py    # SMILES validation and chemistry utility logic.
│   ├── prediction/
│   │   └── Rxn_predict_tool.py
│   ├── retrieval/
│   │   ├── bm25_tool.py      # Persistent sparse retrieval index.
│   │   ├── chroma_tool.py    # Persistent dense retrieval index.
│   │   ├── evaluation.py     # Offline retrieval and groundedness metrics.
│   │   ├── pdf_loader.py     # PDF loading and checksum identity.
│   │   ├── RAG_tool.py       # Ingestion, hybrid search, and RRF fusion.
│   │   ├── reranker.py       # Lazy cross-encoder reranking.
│   │   └── text_splitter.py  # Page-aware chunking.
│   └── verification/
│       ├── Context_verifier.py
│       └── mechaism_verifier.py
├── utils/
│   ├── agent_registry.py   # Central registry of agent callables and middleware.
│   ├── llm.py              # LLM wrapper helpers.
│   └── schema.py           # Typed workflow state definition.
├── docker-compose.yml
├── requirements.txt
└── Readme.MD
```

---

## Component responsibilities

### 1. Agents

- Validator agent
  - Validates the input SMILES string.
  - Canonicalizes it with RDKit.
  - Returns warnings and errors in the state.

- Retriever agent
  - Looks for supporting context from uploaded PDFs.
  - Uses the Chroma-backed vector store.
  - Returns retrieved document chunks with metadata.

- Pre-review agent
  - Creates a payload for human review before the predictor runs.
  - Lets the user approve or modify the planned prediction input.

- Predictor agent
  - Forms the core reaction prediction step.
  - Uses the predictor tool class to preprocess, build prompts, and produce output.

- Verifier agent
  - Checks the predicted output for validity and consistency.
  - Combines RDKit-based validation with context and mechanism scoring.

- Explainer agent
  - Converts the workflow state into a readable explanation report.

- Supervisor agent
  - Orchestrates the whole workflow and manages middleware-driven retries and review.

### 2. Tools

- RDKit tool
  - Performs molecular validation and canonicalization.
  - Checks basic chemistry constraints and structural sanity.

- Prediction tool
  - Encapsulates the reaction prediction lifecycle.
  - Currently uses a placeholder model call and formatting flow.

- Retrieval tools
  - Load PDFs, split them into page-aware chunks, and index them in Chroma and BM25.
  - Retrieve relevant context with dense search, sparse search, RRF fusion, and cross-encoder reranking.

- Verification tools
  - Score the quality of retrieved context and chemistry mechanism alignment.

### 3. Middleware and control flow

- Retry middleware
  - Decides whether to retry from the predictor or retriever stage based on validation failures.

- Post-review middleware
  - Decides whether a human review interruption is needed after prediction and verification.

- Limits middleware
  - Helps cap tool or model usage in the workflow.

---

## Shared workflow state

The workflow relies on a typed state object defined in the schema layer. This state carries:

- the user input and task type,
- SMILES and canonical SMILES,
- reaction conditions,
- uploaded and ingested documents,
- retrieved context chunks,
- prediction output and confidence,
- verification results and scores,
- human feedback,
- explanation report,
- warnings,
- retry counts,
- current workflow status,
- and current active agent.

This state is the backbone of the system and is passed from one agent to the next.

---

## Retrieval V2 and document ingestion flow

The retrieval pipeline is built around these steps:

1. A PDF is loaded, validated, and assigned a SHA-256 document identity.
2. Pages are split into 1,200-character chunks with 150-character overlap while preserving page metadata.
3. Stable chunk IDs prevent duplicate records in both Chroma and BM25.
4. Chunks are indexed in Chroma for semantic search and a local JSON-backed BM25 index for exact chemistry terms.
5. A query is built from the canonical reaction, mechanism, and sorted conditions.
6. Dense and sparse candidates are fused with reciprocal-rank fusion.
7. Up to 30 fused candidates are reranked with a lazy cross-encoder; up to 8 cited chunks are placed in workflow state.
8. If the reranker is unavailable, the top fused candidates are returned with a warning.

This gives the predictor and verifier access to literature-based context.

---

## Current implementation status

| Area | Status |
| --- | --- |
| SMILES validation | Implemented |
| Molecule canonicalization | Implemented |
| PDF loading | Implemented |
| PDF chunking | Implemented |
| Chroma-based retrieval | Implemented |
| Validation agent | Implemented |
| Retriever agent | Implemented |
| Predictor agent | Implemented with Modal API integration (original reactant order preserved) |
| Verifier agent | Implemented with scoring-based validation + LLM fallbacks |
| Explainer agent | Implemented with fallback template |
| Supervisor orchestration | Implemented as a central planner/executor |
| Human review flow | Implemented as a review interrupt pattern |
| API server | `/predict` endpoint implemented; upload and operational endpoints remain |
| Persistent database integration | Still in progress |
| Full end-to-end UI | Streamlit test UI implemented |
| Retrieval V2 | Implemented: Chroma + BM25 + RRF + cross-encoder fallback |
| Retrieval evaluation | Metric helpers implemented; benchmark dataset/results pending |
| LLM error handling | Fallback scores/reports for credit-limited scenarios |

---

## Setup

### Prerequisites

- Python 3.10+
- A working LLM provider configuration for the wrappers in the project
- Optional but recommended: a prepared Chroma persistence directory

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root with values such as:

```env
Embedding_MODEL=BAAI/bge-small-en-v1.5
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

---

## Important implementation notes

- The prediction pipeline integrates with a deployed Modal API (`MODEL_ENDPOINT`); the tool encapsulates payload building, retries, and postprocessing.
- **Fixed:** Canonical SMILES reorders reactants alphabetically; the predictor now sends `original_smiles` (user input order) to the model while keeping canonical SMILES for validation.
- The retrieval flow ingests the PDF paths supplied in `pdf_context` before running the supervisor; the current API does not yet expose a multipart document-upload endpoint.
- Retrieval V2 also maintains `database/bm25_index.json`; this local JSON index is appropriate for the current development setup, not yet for multi-process production workloads.
- The cross-encoder reranker is lazy-loaded and falls back to RRF results if its model is unavailable.
- **Added:** LLM verification/explanation calls have graceful fallbacks (neutral scores, template reports) when Nemotron API credits are exhausted (402 errors).
- The supervisor is the main integration point for workflow control, retries, and human review.
- The API is usable for the current prediction workflow, but authentication, tenant isolation, durable document lifecycle, and production observability are still needed.
- The project is a strong foundation for a research-oriented chemistry assistant, but it still needs more integration work to become a complete application.

---

## Recommended next steps

- Add multipart document upload and document-management endpoints (`/upload`, `/documents`).
- Replace the Modal prediction model with a higher-quality reaction prediction model or service.
- Expand the verifier logic and make the confidence thresholds more domain-specific.
- Build a labeled retrieval benchmark and track recall@k, reciprocal rank, context relevance, and groundedness across retrieval variants.
- Connect the workflow to persistent storage (PostgreSQL + Alembic) and user history.
- Add authentication (API keys, JWT) and tenant isolation.
- Add observability (LangSmith tracing, Prometheus metrics, structured logging).
- Wire the pre-review human-in-the-loop step into the default prediction workflow.
- Improve the Streamlit UI with conversation history, document management, and visualization.
