from typing import TypedDict, Literal
from utils.schema import ReactionState as State


MIN_CONFIDENCE_THRESHOLD = 0.60

MAX_PREDICTOR_RETRIES = 3
MAX_VERIFIER_RETRIES = 2


class InterruptDecision(TypedDict):
    interrupt: bool
    mode: Literal[
        "post_prediction",
        "none"
    ]
    reason: str


def require_post_prediction_review(
    state: State,
) -> InterruptDecision:
    """
    Decide whether a human review is required
    after prediction and verification.
    """

    results = state.get("validation_results", {})
    scores = state.get("validation_scores", {})
    retries = state.get("retry_count", {})

    confidence = state.get("confidence", 0.0)

    predictor_retry = retries.get("predictor", 0)
    verifier_retry = retries.get("verifier", 0)

    # ----------------------------------------
    # No validation available
    # Retry middleware should already handle it
    # ----------------------------------------

    if not results:
        return {
            "interrupt": False,
            "mode": "none",
            "reason": "Validation results unavailable."
        }

    # ----------------------------------------
    # Product validation failed
    # ----------------------------------------

    if (
        not results.get("product_validation", True)
        and predictor_retry >= MAX_PREDICTOR_RETRIES
        and verifier_retry >= MAX_VERIFIER_RETRIES
    ):
        return {
            "interrupt": True,
            "mode": "post_prediction",
            "reason": "product_validation_failed"
        }

    # ----------------------------------------
    # Low confidence
    # ----------------------------------------

    if (
        confidence < MIN_CONFIDENCE_THRESHOLD
        and predictor_retry >= MAX_PREDICTOR_RETRIES
    ):
        return {
            "interrupt": True,
            "mode": "post_prediction",
            "reason": "low_confidence"
        }

    # ----------------------------------------
    # Mechanism score
    # ----------------------------------------

    if (
        scores.get("mechanism_score", 1.0) < 0.20
        and verifier_retry >= MAX_VERIFIER_RETRIES
    ):
        return {
            "interrupt": True,
            "mode": "post_prediction",
            "reason": "low_mechanism_score"
        }

    # ----------------------------------------
    # Context score
    # ----------------------------------------

    if (
        scores.get("context_score", 1.0) < 0.35
        and verifier_retry >= MAX_VERIFIER_RETRIES
    ):
        return {
            "interrupt": True,
            "mode": "post_prediction",
            "reason": "low_context_score"
        }

    return {
        "interrupt": False,
        "mode": "none",
        "reason": "No human review required."
    }


middleware_post_review = require_post_prediction_review