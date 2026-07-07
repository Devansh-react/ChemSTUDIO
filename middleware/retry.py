from typing import Literal, TypedDict
from utils.schema import ReactionState as State


# -----------------------------
# Retry Limits
# -----------------------------

MAX_PREDICTOR_RETRIES = 3
MAX_RETRIEVER_RETRIES = 2
MAX_VERIFIER_RETRIES = 2
MAX_WORKFLOW_RETRIES = 5


# -----------------------------
# Retry Decision Schema
# -----------------------------

class RetryDecision(TypedDict):
    retry: bool
    target: Literal[
        "validator",
        "retriever",
        "predictor",
        "workflow",
        "none",
    ]
    reason: str


# -----------------------------
# Retry Middleware
# -----------------------------

def should_retry_prediction(state: State) -> RetryDecision:

    results = state.get("validation_results", {})
    retry_count = state.get("retry_count", {})

    predictor_retry = retry_count.get("predictor", 0)
    retriever_retry = retry_count.get("retriever", 0)
    workflow_retry = retry_count.get("workflow", 0)

    # ---------------------------------------------------
    # Safety check
    # ---------------------------------------------------

    if workflow_retry >= MAX_WORKFLOW_RETRIES:
        return {
            "retry": False,
            "target": "none",
            "reason": "Maximum workflow retries exceeded."
        }

    # ---------------------------------------------------
    # No verifier output
    # ---------------------------------------------------

    if not results:
        return {
            "retry": True,
            "target": "validator",
            "reason": "No validation results available."
        }

    # ---------------------------------------------------
    # Product validation
    # Highest priority
    # ---------------------------------------------------

    if not results.get("product_validation", True):

        if predictor_retry >= MAX_PREDICTOR_RETRIES:
            return {
                "retry": False,
                "target": "none",
                "reason": "Maximum predictor retries exceeded."
            }

        return {
            "retry": True,
            "target": "predictor",
            "reason": "Product validation failed."
        }

    # ---------------------------------------------------
    # Mechanism validation
    # ---------------------------------------------------

    if not results.get("mechanism_validation", True):

        if predictor_retry >= MAX_PREDICTOR_RETRIES:
            return {
                "retry": False,
                "target": "none",
                "reason": "Maximum predictor retries exceeded."
            }

        return {
            "retry": True,
            "target": "predictor",
            "reason": "Mechanism validation failed."
        }

    # ---------------------------------------------------
    # Retrieved context validation
    # ---------------------------------------------------

    if not results.get("retrieved_context_validation", True):

        if retriever_retry >= MAX_RETRIEVER_RETRIES:
            return {
                "retry": False,
                "target": "none",
                "reason": "Maximum retriever retries exceeded."
            }

        return {
            "retry": True,
            "target": "retriever",
            "reason": "Retrieved context validation failed."
        }

    # ---------------------------------------------------
    # Everything passed
    # ---------------------------------------------------

    return {
        "retry": False,
        "target": "none",
        "reason": "All validations passed."
    }


# Registry Alias

middleware_verifier = should_retry_prediction