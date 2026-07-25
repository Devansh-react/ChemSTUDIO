from utils.schema import ReactionState as State

def create_prediction_state(
    smiles: str,
    conditions: dict,
    mechanism: str | None = None,
    uploaded_docs: list[str] | None = None,
) -> State:

    return {
        "user_query": f"Predict the product of reaction: {smiles}",
        "task_type": "prediction",

        "smiles": smiles,
        "canonical_smiles": None,
        "conditions": conditions,

        "uploaded_docs": uploaded_docs or [],
        "pdf_ingested": False,
        "external_doc_available": bool(uploaded_docs),
        "retrieved_context": [],

        "prediction": None,
        "confidence": 0.0,
        "mechanism": mechanism,
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
        "current_agent": "supervisor",
        "messages": [],
    }