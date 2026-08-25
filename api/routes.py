from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from agents.supervisor import SupervisorAgent
from graph.state import create_prediction_state
from schemas.request import PredictionRequest
from schemas.response import PredictionResponse
from services.pdf_inestion_services import pdf_upload


router = APIRouter()

@router.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Reaction_Prediction"]
    )
async def predict(request:PredictionRequest):
    state = create_prediction_state(
        smiles=request.reactants,
        conditions=request.conditions,
        mechanism=request.mechanism,
        uploaded_docs=request.pdf_context
    )
    # run this pdf upload in different thread 
    if request.pdf_context:
        ingestion_update = await run_in_threadpool(pdf_upload,state)
        state.update(ingestion_update)
    
    supervisor = SupervisorAgent()
    
    
    result = await run_in_threadpool(
        supervisor.run,
        state
    )
    
    metadata = {
        **(result.get("prediction_metadata") or {}),
        "document_ids": result.get("document_ids", []),
        "ingestion_results": result.get(
            "ingestion_results",
            [],
        ),
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
