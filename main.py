from pprint import pprint

from config import MODEL

from utils.schema import ReactionState as State
 
from utils.agent_registry import AGENT_REGISTRY

from prompts.supervisor_prompt import SUPERVISOR_PROMPT

from agents.supervisor import SupervisorAgent


# ============================================================
# Dummy Skills
# ============================================================

SKILLS = {}

# ============================================================
# Dummy Config
# ============================================================

CONFIG = {}

# ============================================================
# Build Supervisor
# ============================================================

supervisor = SupervisorAgent(

    agent_registry=AGENT_REGISTRY,

    skills=SKILLS,

    config=CONFIG,

    model=MODEL,

    prompt=SUPERVISOR_PROMPT,
)

# ============================================================
# Dummy User Request
# ============================================================
state: State = {
    "user_query": "...",
    "task_type": "prediction",

    "smiles": "CCBr",
    "canonical_smiles": None,
    "conditions": {"reagent": "NaOH"},

    "uploaded_docs": [],
    "pdf_ingested": False,
    "external_doc_available": False,
    "retrieved_context": [],

    "prediction": None,
    "confidence": 0.0,
    "mechanism": None,
    "prediction_metadata": None,

    "validation_results": {},
    "validation_scores": {},

    "human_feedback": {
        "mode": "pre_prediction",
        "decision": "approve",
        "comment": "",
        "edited_fields": {}
    },

    "explanation_report": None,
    "warnings": [],

    "retry_count": {
        "predictor": 0,
        "retriever": 0,
        "verifier": 0,
        "workflow": 0,
    },

    "status": "initialized",

    "messages": [],

    "current_agent": "supervisor",
}


# ============================================================
# Run Workflow
# ============================================================

result = supervisor.run(state)

# ============================================================
# Output
# ============================================================

print("\n========== FINAL STATE ==========\n")

pprint(result)