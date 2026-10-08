from tools.prediction.Rxn_predict_tool import PredictionAPIError, ReactionPredictor
from utils.schema import ReactionState as State

def predict_reaction(state: State):
    """Build the deployed-model request from the shared workflow state."""
    canonical_smiles = state.get("canonical_smiles") or ""
    original_smiles = state.get("smiles") or ""
    mechanism = state.get("mechanism") or ""

    if not canonical_smiles:
        raise ValueError(
            "Prediction requires a validated canonical SMILES string."
        )

    if not mechanism:
        raise ValueError(
            "Prediction requires a reaction mechanism."
        )

    model_request = {
        "canonical_smiles": canonical_smiles,
        "original_smiles": original_smiles,
        "mechanism": mechanism,
        "conditions": state.get("conditions", {}),
        "retrieved_context": state.get("retrieved_context", []),
    }

    try:
        predictor = ReactionPredictor(model_request)
        try:
            prediction_result = predictor.predict()
        finally:
            predictor.close()
    except (PredictionAPIError, ValueError) as error:
        return {
            "prediction": None,
            "confidence": 0.0,
            "mechanism": mechanism,
            "prediction_metadata": None,
            "warnings": state.get("warnings", []) + [
                f"Prediction service unavailable: {error}"
            ],
            "status": "failed",
        }

    return {
        "prediction": prediction_result.get("prediction"),
        "confidence": prediction_result.get("confidence") or 0.0,
        "mechanism": prediction_result.get("mechanism"),
        "prediction_metadata": prediction_result.get("prediction_metadata"),
        "status": "predicted",
    }
