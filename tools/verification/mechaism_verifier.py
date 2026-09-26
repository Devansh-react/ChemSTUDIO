from utils.llm import call_llm


def validate_mechanism(reactant: str, condition: dict, mechanism: str, ouptut: str, context: list):
    prompt = f"""
    You are an expert organic chemist.

    Reactant:
    {reactant}

    Reaction Conditions:
    {condition}

    Predicted Mechanism:
    {mechanism}

    Retrieved Literature Context:
    {context}

    Task:
    Determine whether the predicted reaction mechanism is chemically plausible for the given reactant and reaction conditions, considering the retrieved literature context.

    Assign a confidence score between 0.0 and 1.0:

    1.0 = Strongly supported and chemically plausible.
    0.5 = Partially supported or uncertain.
    0.0 = Contradicts chemistry principles or retrieved context.

    Rules:
    - Consider reaction mechanism feasibility.
    - Consider reagent and condition compatibility.
    - Consider agreement with the retrieved context.
    - Return ONLY a single floating-point number.
    - Do NOT provide any explanation, reasoning, text, markdown, or additional characters.

    Example outputs:
    0.92
    0.48
    0.05
    """
    try:
        response = call_llm(prompt)
        score = response.content if hasattr(response, 'content') else str(response)

        if isinstance(score, str):
            return float(score.strip())
        else:
            return 0.5
    except Exception:
        return 0.5
    