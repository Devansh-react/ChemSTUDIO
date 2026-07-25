import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm_model() -> ChatOpenAI:
    """
    Returns the configured Mistral model.
    """

    api_key = os.getenv("MISTRAL_API_KEY")
    model_name = os.getenv("MISTRAL_MODEL")

    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in environment.")

    if not model_name:
        raise ValueError("MISTRAL_MODEL not found in environment.")

    return ChatOpenAI(
        model=model_name,
        api_key=lambda: api_key,
        temperature=0.7,
        max_retries=2,
        timeout=None,
    )


def call_llm(prompt: str):
    """
    Utility function for direct LLM invocation.
    """

    llm = get_llm_model()
    return llm.invoke(prompt)