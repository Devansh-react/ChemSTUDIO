from typing import Optional, TypedDict, Dict, Any
from utils.schema import ReactionState as State


class PreReviewPayload(TypedDict):
    canonical_smiles: Optional[str]
    conditions: Dict[str, str]
    retrieved_context: list[Dict[str, Any]]
    warnings: list[str]


def build_pre_prediction_review(state: State) -> PreReviewPayload:
    """
    Build the payload shown to the user before
    running the prediction model.

    This function never decides whether to interrupt.
    It simply prepares the review payload.
    """

    return {
        "canonical_smiles": state.get("canonical_smiles", ""),
        "conditions": state.get("conditions", {}),
        "retrieved_context": state.get("retrieved_context", state.get("retrived_context", [])),
        "warnings": state.get("warnings", []),
    }