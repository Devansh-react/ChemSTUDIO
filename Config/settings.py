import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://chemstudio:chemstudio_dev@localhost:5432/chem_process_studio"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    model_endpoint: str = "https://devansh-react--chemstudio-api-fastapi.modal.run"
    mistral_api_key: str | None = None
    nemotron_api_key: str | None = None
    nemotron_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nemotron_base_url: str = "https://openrouter.ai/api/v1"

    chroma_persist_directory: str = "database/chroma"
    chroma_collection_name: str = "chemistry_literature_bge_small"
    bm25_index_path: str = "database/bm25_index.json"

    max_predictor_retries: int = 3
    max_retriever_retries: int = 2
    max_verifier_retries: int = 2
    max_workflow_retries: int = 5

    min_confidence: float = 0.60
    top_k: int = 5
    mmr_k: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()