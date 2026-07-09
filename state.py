from utils.schema import ReactionState as State


def create_prediction_state() -> State:

    return {

        # ---------------------------------------------------
        # User Request
        # ---------------------------------------------------

        "user_query":
            "Predict the product of the following reaction.",

        "task_type":
            "prediction",

        # ---------------------------------------------------
        # Chemical Input
        # ---------------------------------------------------

        "smiles":
            "CCBr",

        "canonical_smiles":
            None,

        "conditions": {

            "reagent":
                "NaOH",

            "solvent":
                "Water",

            "temperature":
                "25 C"
        },

        # ---------------------------------------------------
        # Documents
        # ---------------------------------------------------

        "uploaded_docs": [],

        "pdf_ingested": False,

        "external_doc_available": False,

        "retrieved_context": [],

        # ---------------------------------------------------
        # Prediction
        # ---------------------------------------------------

        "prediction": None,

        "confidence": 0.0,

        "mechanism": None,

        "prediction_metadata": None,

        # ---------------------------------------------------
        # Validation
        # ---------------------------------------------------

        "validation_results": {},

        "validation_scores": {},

        # ---------------------------------------------------
        # Human Review
        # ---------------------------------------------------

        "human_feedback": {

            "mode":
                "pre_prediction",

            "decision":
                "approve",

            "comment":
                "",

            "edited_fields": {}
        },

        # ---------------------------------------------------
        # Output
        # ---------------------------------------------------

        "explanation_report":
            None,

        "warnings": [],

        # ---------------------------------------------------
        # Retry
        # ---------------------------------------------------

        "retry_count": {

            "predictor": 0,
            "retriever": 0,
            "verifier": 0,
            "workflow": 0
        },

        # ---------------------------------------------------
        # Workflow
        # ---------------------------------------------------

        "status":
            "initialized",

        "current_agent":
            "supervisor",

        # ---------------------------------------------------
        # Conversation
        # ---------------------------------------------------

        "messages": []
    }


def create_validation_state() -> State:

    state = create_prediction_state()

    state["user_query"] = "Validate the given SMILES."
    state["task_type"] = "validation"

    return state


def create_explanation_state() -> State:

    state = create_prediction_state()

    state["user_query"] = "Explain the following reaction."
    state["task_type"] = "explanation"

    state["prediction"] = "CCOH"
    state["mechanism"] = "SN2"
    state["confidence"] = 0.94

    return state