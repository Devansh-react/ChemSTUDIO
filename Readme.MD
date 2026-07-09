# Chem Process Studio

Chem Process Studio is an experimental AI-assisted chemistry workflow for reaction prediction, document-grounded retrieval, and explanation generation. The repository combines chemistry tooling, retrieval-augmented generation, and a supervisor-style orchestration layer around a shared workflow state.

> Status: the core building blocks are present, but the system is still in an early / partially integrated stage. The chemistry validation, PDF ingestion, vector retrieval, prediction scaffolding, explanation generation, and middleware orchestration are implemented, while the API layer and some full runtime connections are still being completed.

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
   - If the workflow state indicates that PDF documents were ingested, the retriever builds a query from the canonical SMILES and reaction conditions.
   - It searches the Chroma vector store using retrieval tools and returns relevant document chunks as context.
   - This context is stored in the state as retrieved literature evidence.

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
│   └── main.py             # FastAPI entrypoint scaffold (currently empty).
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
│   │   ├── chroma_tool.py
│   │   ├── pdf_loader.py
│   │   ├── RAG_tool.py
│   │   └── text_splitter.py
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
  - Load PDFs, split them into chunks, and index them in Chroma.
  - Retrieve relevant context using similarity or MMR search.

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

## Retrieval and document ingestion flow

The retrieval pipeline is built around these steps:

1. A PDF is loaded through the PDF loader.
2. The PDF content is split into smaller chunks.
3. The chunks are added to the Chroma vector database.
4. A query is built from the current reaction input.
5. The retriever searches the vector store using similarity or MMR retrieval.
6. The top matching document chunks are attached to the workflow state.

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
| Predictor agent | Implemented as a structured workflow with placeholder prediction logic |
| Verifier agent | Implemented with scoring-based validation |
| Explainer agent | Implemented |
| Supervisor orchestration | Implemented as a central planner/executor |
| Human review flow | Implemented as a review interrupt pattern |
| API server | Still scaffolded |
| Persistent database integration | Still in progress |
| Full end-to-end UI | Not implemented |

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
Embedding_MODEL=sentence-transformers/all-MiniLM-L6-v2
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

---

## Important implementation notes

- The current prediction pipeline is structurally complete but still uses a placeholder prediction implementation inside the reaction predictor tool.
- The retrieval flow depends on PDFs already being ingested into the Chroma database.
- The supervisor is the main integration point for workflow control, retries, and human review.
- The API entrypoint is currently just a scaffold and needs further endpoint implementation before it can run as a usable application.
- The project is a strong foundation for a research-oriented chemistry assistant, but it still needs more integration work to become a complete application.

---

## Recommended next steps

- Implement the FastAPI endpoints for prediction and document ingestion.
- Replace the placeholder prediction logic with a real model or external service.
- Expand the verifier logic and make the confidence thresholds more domain-specific.
- Connect the workflow to persistent storage and user history.
- Add a frontend or interactive interface for end-to-end usage.
