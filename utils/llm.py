import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import APIStatusError

load_dotenv()


def _is_credit_error(error: Exception) -> bool:
    """Check if error is due to credit exhaustion (402)."""
    if isinstance(error, APIStatusError):
        return error.status_code == 402
    if hasattr(error, 'status_code'):
        return error.status_code == 402
    error_str = str(error).lower()
    return '402' in error_str or 'credit' in error_str or 'insufficient' in error_str


def get_mistral_model() -> ChatOpenAI:
    """
    Returns the configured Mistral model (primary).
    Default: direct Mistral API - free tier model.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    model_name = os.getenv("MISTRAL_MODEL", "open-mistral-7b")
    base_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")

    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in environment.")

    return ChatOpenAI(
        model=model_name,
        api_key=lambda: api_key,
        base_url=base_url,
        temperature=0.7,
        max_retries=2,
        timeout=60,
        max_tokens=2048,
    )


def get_nemotron_model() -> ChatOpenAI:
    """
    Returns the configured Nemotron 3 Ultra model (fallback).
    Default: direct NVIDIA API (separate credits from OpenRouter).
    """
    api_key = os.getenv("NEMOTRON_API_KEY")
    model_name = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra")
    base_url = os.getenv("NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1")

    if not api_key:
        raise ValueError("NEMOTRON_API_KEY not found in environment.")

    return ChatOpenAI(
        model=model_name,
        api_key=lambda: api_key,
        base_url=base_url,
        temperature=0.7,
        max_retries=2,
        timeout=60,
        max_tokens=2048,
    )


def get_llm_model() -> ChatOpenAI:
    """
    Returns the primary model (Mistral) with Nemotron as fallback.
    """
    try:
        return get_mistral_model()
    except ValueError:
        return get_nemotron_model()


def call_llm(prompt: str):
    """
    Utility function for direct LLM invocation with fallback on credit errors.
    """
    try:
        llm = get_mistral_model()
        return llm.invoke(prompt)
    except Exception as e:
        if _is_credit_error(e) or isinstance(e, ValueError):
            llm = get_nemotron_model()
            return llm.invoke(prompt)
        raise