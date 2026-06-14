# Chem Process Studio

An AI-assisted chemical reaction prediction platform. Users submit SMILES strings and reaction conditions; the system validates input, retrieves relevant context from documents and curated chemistry data, predicts outcomes, and explains mechanisms with safety notes.

> **Status:** Early development. Core orchestration, API, and frontend layers are planned; RAG retrieval, SMILES validation, and PDF ingestion are in progress.

---

## Architecture

### Mermaid diagram

```mermaid
flowchart TB
    subgraph FE["Frontend Layer"]
        UI["React Web App<br/>SMILES + reaction conditions input"]
    end

    subgraph API["API Layer"]
        GW["API Gateway — FastAPI<br/>JWT auth · /predict · /chat · /upload-model"]
    end

    subgraph ORCH["Orchestration Layer"]
        SUP["Supervisor Agent — LangGraph<br/>Routes tasks · graph state · checkpointing"]
        INP["Input parser<br/>Normalize SMILES + conditions"]
        VAL["Validate SMILES — RDKit<br/>Fail fast on invalid input"]
        CHK["Check conditions<br/>Are conditions present?"]
        HIL["Human-in-loop<br/>Ask user or use standard"]
        RAG["RAG retriever — ChromaDB<br/>User docs + curated chem DB"]
    end

    subgraph TOOLS["Tools Layer"]
        PRED["Ollama predictor — Qwen<br/>Fine-tuned reaction dataset"]
        CRED["Credibility check<br/>RDKit · confidence · DB cross-ref"]
        SAFE["Safety flag check<br/>Toxicity · hazard warnings"]
        EXPL["Gemini / OpenAI explainer<br/>Mechanism · yield · safety notes"]
        RETRY["Retry node<br/>Re-prompt Ollama"]
    end

    subgraph STORE["Storage Layer"]
        PG[("PostgreSQL<br/>Users · history · feedback")]
        CHROMA[("ChromaDB<br/>Vector embeddings · RAG")]
        S3[("S3 / Local<br/>PDFs · model files")]
    end

    UI --> GW
    GW --> SUP
    SUP --> INP --> VAL --> CHK --> RAG --> PRED --> CRED --> SAFE --> EXPL
    EXPL --> GW

    VAL -.->|invalid| GW
    CHK -.->|missing| HIL
    HIL --> CHK
    CRED -.->|low conf.| RETRY
    RETRY --> PRED
    EXPL -.->|error| RETRY

    RAG -.-> CHROMA
    GW -.-> PG
    RAG -.-> S3
    PRED -.-> S3
```

---

## Tech stack

| Layer         | Technologies                                  |
| ------------- | --------------------------------------------- |
| Frontend      | React (planned)                               |
| API           | FastAPI, JWT auth (planned)                   |
| Orchestration | LangGraph, LangChain                          |
| Chemistry     | RDKit, PubChemPy, SELFIES                     |
| Prediction    | Ollama / Qwen (planned)                       |
| Explanation   | Google Gemini, OpenAI (planned)               |
| RAG           | ChromaDB, HuggingFace embeddings, PyPDF       |
| Storage       | PostgreSQL, Redis, ChromaDB, S3 / local files |

---

## Project structure

```
Chem_Procress_studio/
├── agents/                 # LangGraph agent nodes
│   ├── retriever.py        # RAG context retrieval
│   └── validator.py        # SMILES validation & condition checks
├── graph/                  # LangGraph workflow & routing
│   └── router.py
├── Services/               # Service-layer handlers
│   └── pdf_inestion_services.py
├── tools/
│   ├── chemistry/          # RDKit utilities
│   ├── prediction/         # Reaction prediction (planned)
│   └── retrieval/          # PDF loading, chunking, ChromaDB
├── utils/
│   └── schemas_chat.py     # Shared state schemas (ReactionState)
├── requirements.txt
└── Arciture_Diagram.png
```

---

## Getting started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) (for local prediction, planned)
- PostgreSQL (planned)
- Node.js (for frontend, planned)

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd Chem_Procress_studio

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root:

```env
Embedding_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Planned
# OPENAI_API_KEY=
# GOOGLE_API_KEY=
# DATABASE_URL=postgresql://user:pass@localhost/chem_studio
```

---

## Current implementation

| Component                           | Status      |
| ----------------------------------- | ----------- |
| SMILES validation (RDKit)           | In progress |
| PDF ingestion & chunking            | In progress |
| ChromaDB vector store & retrieval   | In progress |
| Retriever agent                     | In progress |
| LangGraph supervisor & routing      | Planned     |
| FastAPI endpoints                   | Planned     |
| Reaction prediction (Ollama / Qwen) | Planned     |
| Credibility & safety checks         | Planned     |
| LLM explainer                       | Planned     |
| React frontend                      | Planned     |
| PostgreSQL persistence              | Planned     |

---

## API endpoints (planned)

| Method | Endpoint        | Description                                       |
| ------ | --------------- | ------------------------------------------------- |
| `POST` | `/predict`      | Predict reaction outcome from SMILES + conditions |
| `POST` | `/chat`         | Conversational chemistry assistant                |
| `POST` | `/upload-model` | Upload custom model or reference documents        |

---

## License

TBD

## Contributing

This project is under active development. Contribution guidelines will be added as the codebase stabilizes.
