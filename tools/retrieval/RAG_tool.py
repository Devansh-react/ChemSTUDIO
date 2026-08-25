"""PDF ingestion and hybrid retrieval for chemistry literature."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import json
from typing import Any, Iterable

from tools.retrieval.bm25_tool import (
    add_documents as add_to_bm25,
)
from tools.retrieval.bm25_tool import sparse_search
from tools.retrieval.chroma_tool import (
    add_document as add_to_chroma,
)
from tools.retrieval.chroma_tool import (
    dense_search,
    mmr_search,
    similarity_score_threshold,
)
from tools.retrieval.pdf_loader import pdf_loader
from tools.retrieval.text_splitter import split_documents


DENSE_CANDIDATE_COUNT = 40
SPARSE_CANDIDATE_COUNT = 40
RRF_CONSTANT = 60
RRF_CANDIDATE_COUNT = 30
RETRIEVAL_CACHE_SIZE = 128

_hybrid_retrieval_cache: OrderedDict[
    str,
    list[dict[str, Any]],
] = OrderedDict()


def _build_cache_key(
    query: str,
    k: int,
    dense_k: int,
    sparse_k: int,
    metadata_filter: dict[str, Any] | None,
) -> str:
    """Create a stable key for an in-process hybrid retrieval cache."""
    return json.dumps(
        {
            "query": " ".join(query.split()),
            "k": k,
            "dense_k": dense_k,
            "sparse_k": sparse_k,
            "metadata_filter": metadata_filter,
        },
        sort_keys=True,
        default=str,
    )


def _cache_hybrid_results(
    cache_key: str,
    candidates: list[dict[str, Any]],
) -> None:
    """Store a bounded cache entry and evict the least-recently-used one."""
    _hybrid_retrieval_cache[cache_key] = deepcopy(candidates)
    _hybrid_retrieval_cache.move_to_end(cache_key)

    if len(_hybrid_retrieval_cache) > RETRIEVAL_CACHE_SIZE:
        _hybrid_retrieval_cache.popitem(last=False)


def ingest_pdf(pdf_path: str) -> dict[str, Any]:
    """
    Load, split, and index one PDF in both retrieval engines.

    Chroma and BM25 use the same stable chunk IDs. This lets RRF identify
    a chunk that appears in results from both retrieval engines.
    """
    pages = pdf_loader(pdf_path)
    chunks = split_documents(pages)

    if not chunks:
        raise ValueError(
            "No searchable chunks were created from the PDF."
        )

    document_id = str(
        pages[0].metadata.get("document_id", "")
    )

    document_checksum = str(
        pages[0].metadata.get("document_checksum", "")
    )

    total_pages = int(
        pages[0].metadata.get(
            "total_pages",
            len(pages),
        )
    )

    for chunk in chunks:
        chunk.metadata["document_id"] = document_id
        chunk.metadata["document_checksum"] = document_checksum
        chunk.metadata["total_pages"] = total_pages

    chroma_result = add_to_chroma(chunks)
    bm25_result = add_to_bm25(chunks)
    _hybrid_retrieval_cache.clear()

    return {
        "document_id": document_id,
        "pdf_name": pages[0].metadata.get("pdf_name"),
        "total_pages": total_pages,
        "chunks_created": len(chunks),
        "chroma": chroma_result,
        "bm25": bm25_result,
    }


def reciprocal_rank_fusion(
    ranked_result_sets: Iterable[
        tuple[str, list[dict[str, Any]]]
    ],
    rrf_constant: int = RRF_CONSTANT,
    limit: int = RRF_CANDIDATE_COUNT,
) -> list[dict[str, Any]]:
    """
    Combine ranked dense and sparse result lists using RRF.

    RRF combines ranking positions, not raw scores. This is necessary
    because Chroma distances and BM25 scores are not directly comparable.
    """
    fused_by_chunk_id: dict[str, dict[str, Any]] = {}

    for engine_name, candidates in ranked_result_sets:
        for rank, candidate in enumerate(
            candidates,
            start=1,
        ):
            chunk_id = candidate["chunk_id"]

            if chunk_id not in fused_by_chunk_id:
                fused_by_chunk_id[chunk_id] = {
                    "chunk_id": chunk_id,
                    "content": candidate["content"],
                    "metadata": candidate["metadata"],
                    "rrf_score": 0.0,
                    "dense_rank": None,
                    "bm25_rank": None,
                    "dense_distance": None,
                    "bm25_score": None,
                }

            fused_candidate = fused_by_chunk_id[chunk_id]

            fused_candidate["rrf_score"] += 1 / (
                rrf_constant + rank
            )

            if engine_name == "dense":
                fused_candidate["dense_rank"] = rank
                fused_candidate["dense_distance"] = candidate.get(
                    "dense_distance"
                )

            elif engine_name == "sparse":
                fused_candidate["bm25_rank"] = rank
                fused_candidate["bm25_score"] = candidate.get(
                    "bm25_score"
                )

    fused_candidates = list(
        fused_by_chunk_id.values()
    )

    fused_candidates.sort(
        key=lambda candidate: candidate["rrf_score"],
        reverse=True,
    )

    final_candidates = fused_candidates[:limit]

    for rank, candidate in enumerate(
        final_candidates,
        start=1,
    ):
        candidate["rank"] = rank

    return final_candidates


def hybrid_retrieve_context(
    query: str,
    k: int = RRF_CANDIDATE_COUNT,
    dense_k: int = DENSE_CANDIDATE_COUNT,
    sparse_k: int = SPARSE_CANDIDATE_COUNT,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve dense and sparse candidates, then combine them with RRF.

    This returns RRF candidates for the next cross-encoder reranking step.
    It does not yet return the final LLM context.
    """
    if not query.strip():
        return []

    cache_key = _build_cache_key(
        query=query,
        k=k,
        dense_k=dense_k,
        sparse_k=sparse_k,
        metadata_filter=metadata_filter,
    )

    cached_candidates = _hybrid_retrieval_cache.get(cache_key)
    if cached_candidates is not None:
        _hybrid_retrieval_cache.move_to_end(cache_key)
        return deepcopy(cached_candidates)

    dense_candidates = dense_search(
        query=query,
        k=dense_k,
        metadata_filter=metadata_filter,
    )

    sparse_candidates = sparse_search(
        query=query,
        k=sparse_k,
        metadata_filter=metadata_filter,
    )

    fused_candidates = reciprocal_rank_fusion(
        ranked_result_sets=[
            ("dense", dense_candidates),
            ("sparse", sparse_candidates),
        ],
        limit=k,
    )

    _cache_hybrid_results(cache_key, fused_candidates)

    return fused_candidates

# [
#     {
#         "chunk_id": "abc123",
#         "content": "Polar aprotic solvents favor SN2 reactions...",
#         "metadata": {
#             "pdf_name": "reaction_study.pdf",
#             "page": 4
#         },
#         "rrf_score": 0.03151,
#         "dense_rank": 2,
#         "bm25_rank": 5,
#         "rank": 1
#     }
# ]

# Compatibility functions for existing code.
# They can be removed after agents/retriever.py is updated.

def retrieve_context(
    query: str,
    k: int = 5,
):
    """Return hybrid RRF candidates."""
    return hybrid_retrieve_context(
        query=query,
        k=k,
    )

def retrieve_context_mmr(
    query: str,
    k: int = 5,
):
    """Legacy dense-only MMR retrieval."""
    return mmr_search(
        query=query,
        k=k,
    )

def retrieve_context_similarity(
    query: str,
    k: int = 5,
):
    """Legacy thresholded dense retrieval."""
    return similarity_score_threshold(
        query=query,
        k=k,
    )
