from fastapi import APIRouter
from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from agents.supervisor import SupervisorAgent
from graph.state import create_prediction_state
from schemas.request import PredictionRequest
from schemas.response import PredictionResponse
from services.pdf_inestion_services import pdf_upload

from database.models import User  
from api.auth import get_current_user, require_predict_scope

router = APIRouter()

@router.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Reaction_Prediction"],
    dependencies=[Depends(require_predict_scope)],  # ADD SCOPE CHECK HERE
)
async def predict(
    request: PredictionRequest,
    user: User = Depends(get_current_user),  # ADD USER DEPENDENCY
):
    # Attach user_id to request for document ownership
    request.user_id = str(user.id)

    state = create_prediction_state(
        smiles=request.reactants,
        conditions=request.conditions,
        mechanism=request.mechanism,
        uploaded_docs=request.pdf_context,
    )

    
    supervisor = SupervisorAgent()
    
    
    result = await run_in_threadpool(
        supervisor.run,
        state
    )
    
    metadata = {
        **(result.get("prediction_metadata") or {}),
        "document_ids": result.get("document_ids", []),
        "ingestion_results": result.get("ingestion_results",[],),
        "retrieved_context": result.get("retrieved_context", []),
    }
    return PredictionResponse(
        success=result["status"] == "completed",
        prediction=result.get("prediction"),
        mechanism=result.get("mechanism"),
        explanation=result.get("explanation_report"),
        verification={
            "results": result.get("validation_results"),
            "scores": result.get("validation_scores"),
        },
        metadata=metadata,
        warnings=result.get("warnings", []),
    )
