"""Offline evaluation helpers for the RAG v2 retrieval pipeline."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable


def context_relevance(
    retrieved_chunk_ids: Iterable[str],
    relevant_chunk_ids: Iterable[str],
) -> float:
    """Relevant retrieved chunks divided by all retrieved chunks."""
    retrieved = list(retrieved_chunk_ids)
    relevant = set(relevant_chunk_ids)

    if not retrieved:
        return 0.0

    return sum(
        chunk_id in relevant
        for chunk_id in retrieved
    ) / len(retrieved)


def recall_at_k(
    retrieved_chunk_ids: Iterable[str],
    relevant_chunk_ids: Iterable[str],
    k: int,
) -> float:
    """Relevant chunks found in the first k results divided by all relevant chunks."""
    if k <= 0:
        return 0.0

    relevant = set(relevant_chunk_ids)
    if not relevant:
        return 0.0

    retrieved_at_k = set(list(retrieved_chunk_ids)[:k])
    return len(retrieved_at_k & relevant) / len(relevant)


def reciprocal_rank(
    retrieved_chunk_ids: Iterable[str],
    relevant_chunk_ids: Iterable[str],
) -> float:
    """Return the reciprocal rank of the first relevant retrieved chunk."""
    relevant = set(relevant_chunk_ids)

    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / rank

    return 0.0


def groundedness(
    claim_support: Iterable[bool],
) -> float:
    """Supported answer claims divided by all verifiable answer claims."""
    support_results = list(claim_support)

    if not support_results:
        return 0.0

    return sum(support_results) / len(support_results)


def build_answer_relevance_prompt(
    question: str,
    answer: str,
) -> str:
    """Create a strict rubric prompt for an offline LLM-as-judge evaluation."""
    return f"""You are evaluating whether an answer addresses a user question.

Question:
{question}

Answer:
{answer}

Score answer relevance from 0.0 to 1.0.
1.0 means the answer directly and completely addresses the question.
0.5 means it is partially relevant or misses important requested information.
0.0 means it is irrelevant.

Return only one number between 0.0 and 1.0.
"""


def answer_relevance(
    question: str,
    answer: str,
    judge: Callable[[str], object],
) -> float:
    """
    Score answer relevance with an injected LLM judge.

    Keep this offline or sampled in production because it adds an LLM call.
    The `judge` callable receives the generated rubric prompt.
    """
    response = judge(
        build_answer_relevance_prompt(question, answer)
    )

    response_text = getattr(response, "content", str(response))
    number_match = re.search(
        r"(?:0(?:\.\d+)?|1(?:\.0+)?)",
        response_text,
    )

    if not number_match:
        raise ValueError(
            "LLM judge did not return a numeric relevance score."
        )

    return float(number_match.group(0))
