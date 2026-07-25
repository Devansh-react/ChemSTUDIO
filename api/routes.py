from fastapi import APIRouter

from schemas.request import PredictionRequest
from schemas.response import PredictionResponse

from agents.supervisor import SupervisorAgent
from graph.state import create_prediction_state

router = APIRouter()


@router.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Reaction Prediction"],
)
async def predict(request: PredictionRequest):

    state = create_prediction_state(
        smiles=request.reactants,
        conditions=request.conditions,
        mechanism=request.mechanism,
        uploaded_docs=request.pdf_context,
    )

    supervisor = SupervisorAgent()

    result = supervisor.run(state)

    return PredictionResponse(
    success=result["status"] == "completed",
    prediction=result.get("prediction"),
    mechanism=result.get("mechanism"),
    explanation=result.get("explanation_report"),
    verification={
        "results": result.get("validation_results"),
        "scores": result.get("validation_scores"),
    },
    metadata=result.get("prediction_metadata") or {},
    warnings=result["warnings"],
)