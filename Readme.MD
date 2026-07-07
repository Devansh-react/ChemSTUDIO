<p align="center">
  <img src="logo.png" alt="Chem Process Studio logo" width="80%"/>
</p>

# Chem Process Studio

Chem Process Studio is an early-stage AI-assisted chemistry workflow for reaction prediction, document-grounded context retrieval, and explanation generation. The current codebase combines chemistry tooling, retrieval-augmented generation, and agent-oriented orchestration around a shared workflow state.

> Status: partially implemented. Core chemistry validation, PDF ingestion, vector retrieval, prediction scaffolding, explanation generation, and middleware modules are present, while the API layer and some orchestration pieces are still being completed.

---

## What is implemented today

- SMILES validation and canonicalization with RDKit
- PDF loading, chunking, and ingestion for retrieval
- Chroma-based vector storage and retrieval using similarity and MMR search
- A typed workflow state for reaction-related tasks
- Agent modules for validation, retrieval, prediction, explanation, verifier, supervisor, and human review
- Middleware helpers for retries, human review conditions, model/tool limits, and logging scaffolding
- A service layer for PDF ingestion

---

## High-level workflow

1. A user provides a SMILES string and reaction conditions.
2. The validation agent checks whether the molecule is syntactically valid and structurally acceptable.
3. Uploaded PDFs can be ingested into the retrieval system for external context.
4. The retriever searches the indexed documents for relevant chemistry context.
5. The predictor builds a reaction prediction output using the current tool pipeline.
6. The explainer converts the workflow state into a readable report.
7. Retry and human-review hooks can be triggered based on validation and confidence conditions.

---

## Tech stack

- Python 3.10+
- FastAPI (API entrypoint scaffolded)
- LangChain and LangGraph-based agent orchestration
- RDKit for chemistry validation
- ChromaDB with HuggingFace embeddings for retrieval
- PyPDF and text splitting utilities for document ingestion
- Google/OpenAI LLM wrappers via LangChain
- PostgreSQL and Docker support are planned but not yet fully wired in

---

## Repository structure

```text
Chem_Procress_studio/
├── agents/
│   ├── explainer.py
│   ├── human_review.py
│   ├── predictor.py
│   ├── retriever.py
│   ├── supervisor.py
│   ├── validator.py
│   └── verifier.py
├── api/
│   └── main.py
├── database/
│   ├── chroma/
│   └── postgress/
├── graph/
│   └── state.py
├── middleware/
│   ├── guardrails.py
│   ├── interrupts.py
│   ├── limits.py
│   ├── logging.py
│   └── retry.py
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
│   │   └── RDKit_tool.py
│   ├── prediction/
│   │   └── Rxn_predict_tool.py
│   ├── retrieval/
│   │   ├── chroma_tool.py
│   │   ├── pdf_loader.py
│   │   ├── RAG_tool.py
│   │   └── text_splitter.py
│   └── verification/
│       ├── Context_verifier.py
│       └── mechaism_verifier.py
├── utils/
│   ├── agent_registry.py
│   ├── llm.py
│   └── schema.py
├── docker-compose.yml
├── requirements.txt
└── Readme.MD
```

---

## Setup

### Prerequisites

- Python 3.10+
- A compatible LLM provider configuration for the LangChain wrappers
- Optional: Chroma persistence directory already prepared under the project database folder

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root with values such as:

```env
Embedding_MODEL=sentence-transformers/all-MiniLM-L6-v2
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

---

## Current implementation status

| Area | Status |
| --- | --- |
| SMILES validation | Implemented |
| Molecule canonicalization | Implemented |
| PDF ingestion | Implemented |
| Document chunking | Implemented |
| Chroma-based retrieval | Implemented |
| Validation agent | Implemented |
| Retriever agent | Implemented |
| Predictor agent | Scaffolded with a placeholder pipeline |
| Explainer agent | Implemented |
| Verifier agent | Present as module scaffolding |
| Supervisor orchestration | Partial / in progress |
| FastAPI endpoints | Not yet implemented |
| Frontend | Not yet implemented |
| Database persistence | Planned |

---

## Notes on the current codebase

- The prediction flow is functional at the orchestration level but still uses an internal placeholder implementation in the reaction predictor tool.
- The retrieval flow depends on ingested documents being available in the Chroma store.
- The API server is currently a stub and needs endpoint definitions before it can be used as an application interface.
- The middleware files are present and can be expanded for stricter guardrails, retries, and human review handling.

---

## Next steps

- Implement FastAPI endpoints for prediction and document ingestion
- Replace the placeholder prediction logic with a real model or external service
- Expand verifier logic and confidence-based routing
- Connect persistent storage and user history flows
- Add a frontend interface for end-to-end usage
