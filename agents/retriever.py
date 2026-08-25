"""Literature retrieval agent for the reaction-prediction workflow."""

from __future__ import annotations

from typing import Any

from tools.retrieval.RAG_tool import hybrid_retrieve_context
from tools.retrieval.reranker import rerank_candidates
from utils.schema import ReactionState


RRF_CANDIDATE_COUNT = 30
FINAL_CONTEXT_COUNT = 8


def build_chemistry_query(state: ReactionState) -> str:
    """Build one consistent query for dense and BM25 retrieval."""
    reactants = (
        state.get("canonical_smiles")
        or state.get("smiles")
        or "Not provided"
    )

    mechanism = state.get("mechanism") or "Not provided"
    conditions = state.get("conditions") or {}

    formatted_conditions = "\n".join(
        f"- {name}: {value}"
        for name, value in sorted(conditions.items())
        if value is not None and value != ""
    )

    if not formatted_conditions:
        formatted_conditions = "- Not provided"

    return f"""Reaction literature retrieval

    Reactants (canonical SMILES):
    {reactants}

    Requested or predicted mechanism:
    {mechanism}

    Reaction conditions:
    {formatted_conditions}

    Find experimental evidence, comparable reactions, compatible conditions,
    mechanistic support, and reported products relevant to this reaction.
    """


def _format_context(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep evidence, citations, and retrieval diagnostics in state."""
    context: list[dict[str, Any]] = []

    for candidate in candidates:
        metadata = candidate.get("metadata", {})

        context.append(
            {
                "chunk_id": candidate.get("chunk_id"),
                "content": candidate.get("content", ""),
                "source": metadata.get("pdf_name"),
                "page": metadata.get("page"),
                "section": metadata.get("section_heading"),
                "metadata": metadata,
                "retrieval": {
                    "rrf_rank": candidate.get("rank"),
                    "rrf_score": candidate.get("rrf_score"),
                    "dense_rank": candidate.get("dense_rank"),
                    "bm25_rank": candidate.get("bm25_rank"),
                    "reranker_rank": candidate.get("reranker_rank"),
                    "reranker_score": candidate.get("reranker_score"),
                },
            }
        )

    return context


def retriever_agent(state: ReactionState) -> dict[str, Any]:
    """
    Retrieve literature evidence for a reaction.

    Pipeline:
        chemistry-aware query
        → Chroma dense search + local BM25 sparse search
        → Reciprocal Rank Fusion
        → cross-encoder reranking
        → cited evidence stored in state
    """
    pdf_ingested = bool(
        state.get(
            "pdf_ingested",
            state.get("pdf_injested", False),
        )
    )

    if not pdf_ingested:
        return {
            "external_doc_available": False,
            "retrieved_context": [],
        }

    query = build_chemistry_query(state)

    rrf_candidates = hybrid_retrieve_context(
        query=query,
        k=RRF_CANDIDATE_COUNT,
    )

    if not rrf_candidates:
        return {
            "external_doc_available": True,
            "retrieved_context": [],
            "warnings": state.get("warnings", []) + [
                "No relevant literature chunks were found."
            ],
        }

    try:
        final_candidates = rerank_candidates(
            query=query,
            candidates=rrf_candidates,
            top_k=FINAL_CONTEXT_COUNT,
        )
    except Exception as error:
        # Retrieval remains useful if the optional reranker model is offline.
        final_candidates = rrf_candidates[:FINAL_CONTEXT_COUNT]

        return {
            "external_doc_available": True,
            "retrieved_context": _format_context(final_candidates),
            "warnings": state.get("warnings", []) + [
                f"Reranker unavailable; using RRF results. {error}"
            ],
        }

    return {
        "external_doc_available": True,
        "retrieved_context": _format_context(final_candidates),
    }
