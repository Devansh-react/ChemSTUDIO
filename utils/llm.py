import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm_model() -> ChatOpenAI:
    """
    Returns the configured Nemotron 3 Ultra model.
    """

    api_key = os.getenv("NEMOTRON_API_KEY")
    model_name = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    base_url = os.getenv("NEMOTRON_BASE_URL", "https://openrouter.ai/api/v1")

    if not api_key:
        raise ValueError("NEMOTRON_API_KEY not found in environment.")

    if not model_name:
        raise ValueError("NEMOTRON_MODEL not found in environment.")

    return ChatOpenAI(
        model=model_name,
        api_key=lambda: api_key,
        base_url=base_url,
        temperature=0.7,
        max_retries=2,
        timeout=60,
        max_tokens=2048,
    )


def call_llm(prompt: str):
    """
    Utility function for direct LLM invocation.
    """

    llm = get_llm_model()
    return llm.invoke(prompt)