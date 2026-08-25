"""Cross-encoder reranking for hybrid retrieval candidates."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from sentence_transformers import CrossEncoder

load_dotenv()

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)


class CrossEncoderReranker:
    """
    Score query-and-chunk pairs with a cross-encoder.

    Unlike the embedding model, a cross-encoder reads the complete query and
    chunk together. It is used only after RRF, where the candidate set is small.
    """

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self.model_name = model_name
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        """Load the reranking model only when the first search needs it."""
        if self._model is None:
            self._model = CrossEncoder(self.model_name)

        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        """
        Return the best RRF candidates ordered by cross-encoder relevance.

        Every returned candidate keeps its RRF score, dense rank, BM25 rank,
        text, and citation metadata for later debugging and explanation.
        """
        if not query.strip() or not candidates or top_k <= 0:
            return []

        pairs = [
            (query, candidate["content"])
            for candidate in candidates
            if candidate.get("content")
        ]

        valid_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("content")
        ]

        if not pairs:
            return []

        scores = self.model.predict(pairs)

        scored_candidates: list[dict[str, Any]] = []

        for candidate, score in zip(valid_candidates, scores):
            reranked_candidate = dict(candidate)
            reranked_candidate["reranker_score"] = float(score)
            reranked_candidate["reranker_model"] = self.model_name
            scored_candidates.append(reranked_candidate)

        scored_candidates.sort(
            key=lambda candidate: candidate["reranker_score"],
            reverse=True,
        )

        final_candidates = scored_candidates[:top_k]

        for rank, candidate in enumerate(final_candidates, start=1):
            candidate["reranker_rank"] = rank

        return final_candidates


reranker = CrossEncoderReranker()


def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Rerank RRF candidates through the shared lazy-loaded model."""
    return reranker.rerank(
        query=query,
        candidates=candidates,
        top_k=top_k,
    )
