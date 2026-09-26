from utils.llm import call_llm
from typing import List, Dict

def verify_prediction_with_context(prediction_mechanism: str, retrived_context: List[Dict], confidence: float = 0.0):
    if not prediction_mechanism or not retrived_context:
        return 0.0
    prompt = f"""
    You are an expert organic chemist.

    Predicted Mechanism:
    {prediction_mechanism}

    Retrieved Literature Context:
    {retrived_context}

    Model Confidence Score:
    {confidence}

    Task:
    Re-evaluate the prediction by considering:

    1. Whether the mechanism is supported by the retrieved literature.
    2. Whether the model confidence score appears reasonable.
    3. Whether the literature and confidence score are consistent with each other.

    Assign a final confidence score between 0.0 and 1.0:

    1.0 = Strong agreement between mechanism, literature, and confidence.
    0.5 = Partial agreement or uncertainty.
    0.0 = Major contradictions.

    Rules:
    - Return ONLY a single floating-point number.
    - Do NOT explain your reasoning.
    - Do NOT output JSON.
    - Do NOT output labels or text.
    - Output must contain only one number.

    Example outputs:
    0.88
    0.53
    0.12
    """
    try:
        response = call_llm(prompt)
        score = response.content if hasattr(response, 'content') else str(response)

        if isinstance(score, str):
            try:
                score = float(score.strip())
            except ValueError:
                score = 0.0

        return score
    except Exception:
        return 0.0