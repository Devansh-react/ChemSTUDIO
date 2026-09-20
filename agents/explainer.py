from utils.schema import ReactionState as State 
from utils.llm import call_llm


def explainer_agent(state:State):
    prediction = state.get("prediction","")
    mechnanism = state.get("mechanism","")
    prediction_metadata = state.get("prediction_metadata",{})
    validation_results = state.get("validation_results",{})
    validation_scores = state.get("validation_scores",{})
    warnings = state.get("warnings",[])
    
    prompt = f"""
    You are an Explanation Agent.

    Your job is ONLY to convert the provided system state into a clear, human-readable report.

    Rules:
    - Do NOT generate new predictions.
    - Do NOT change the prediction, mechanism, confidence, or validation results.
    - Do NOT add chemistry knowledge, assumptions, or recommendations.
    - Do NOT infer missing information.
    - Use only the information provided below.
    - If any field is empty, write "Not Available".

    Prediction:
    {prediction}

    Mechanism:
    {mechnanism}

    Prediction Metadata:
    {prediction_metadata}

    Validation Results:
    {validation_results}

    Validation Scores:
    {validation_scores}

    Warnings:
    {warnings}

    Generate a concise report with the following sections:

    1. Prediction Summary
    2. Mechanism Summary
    3. Prediction Metadata
    4. Validation Summary
    5. Warnings
    6. Final System Status

    The report must only rephrase and structure the information above for readability.
    """
    response = call_llm(prompt)
    
    return {
        "explanation_report": response.content if hasattr(response, "content") else str(response)
    }
