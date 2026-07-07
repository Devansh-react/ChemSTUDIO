from utils.schema import ReactionState as State
from langgraph.types import interrupt
from utils.schema import HumanFeedback 
from typing import Literal

def build_pre_payload(state:State):
    canonical_smiles_input = state.get("canonical_smiles","")
    conditions = state.get("conditions",{})
    retrieved_context = state.get("retrieved_context", state.get("retrived_context", []))
    Warning = state.get("warnings",[])
    
    if not retrieved_context:
        retrieved_context = ["No document is provided by you"]
        
    return {
        "mode":"pre_prediction",
        "canonical_smiles":canonical_smiles_input,
        "conditions":conditions,
        "retrieved_context":retrieved_context,
        "warnings":Warning,
        "actions": ["approve","modify","reject"]
    }

def build_post_payload(state:State):
    predictions = state.get("prediction","")
    confidence_retrived = state.get("confidence",0.0)
    mechanism_retrived = state.get("mechanism","")
    prediction_metadata = state.get("prediction_metadata",{})
    validation_results = state.get("validation_results",{})
    validation_scores = state.get("validation_scores",{})
    retry_counts = state.get("retry_count",{})
    

    return {
        "mode":"post_prediction",
        "prediction":predictions,
        "confidence":confidence_retrived,
        "mechanism":mechanism_retrived,
        "prediction_metadata":prediction_metadata,
        "validation_results":validation_results,
        "validation_scores":validation_scores,
        "retry_counts":retry_counts,
        "actions":["approve","modify","reject","retry"]
    }

def update_human_feedback(
    state: State,
    response: HumanFeedback
):

    state["human_feedback"] = response

    return state
    


def human_review_agent(
    state: State,
    mode: Literal[
        "pre_prediction",
        "post_prediction"
    ]
) -> State:

    if mode == "pre_prediction":
        payload = build_pre_payload(state)

    else:
        payload = build_post_payload(state)

    response = interrupt(payload)

    valid_actions = payload["actions"]

    decision = response.get("decision")

    if decision not in valid_actions:
        raise ValueError(
            f"Invalid decision : {decision}"
        )
    response  = HumanFeedback(
        mode = mode,
        decision = decision,
        comment = response.get("comment"),
        edited_fields = response.get("edited_fields")
    )
    updated_state = update_human_feedback(
        state,
        response
    )
    return updated_state

