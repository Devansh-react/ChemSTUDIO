from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from tools.retrieval.chroma_tool import build_chunk_id


BM25_INDEX_PATH = Path(
    os.getenv(
        "BM25_INDEX_PATH",
        "database/bm25_index.json",
    )
)

# It is not a chemical parser—it simply preserves more chemistry-style text than basic word splitting.
TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9+.#=()\-]*"
)


def tokenize(text: str) -> list[str]:
    """
    Convert text into BM25 search terms.

    Chemistry terms such as SN2, NaBH4, Pd/C, DMF, and Cu(I) are kept
    more usefully than with a basic word-only tokenizer.
    """
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
    ]


def _matches_metadata_filter(
    metadata: dict[str, Any],
    metadata_filter: dict[str, Any] | None,
) -> bool:
    """Match simple equality filters and Chroma-compatible `$in` filters."""
    if not metadata_filter:
        return True

    for key, expected_value in metadata_filter.items():
        actual_value = metadata.get(key)

        if isinstance(expected_value, dict) and "$in" in expected_value:
            if actual_value not in expected_value["$in"]:
                return False
        elif actual_value != expected_value:
            return False

    return True


class LocalBM25Index:
    """
    A small persistent BM25 index stored as JSON.

    Suitable for the current local Chroma development setup.
    It can be replaced later with Elasticsearch, OpenSearch, or Pinecone
    sparse retrieval without changing the higher-level RAG pipeline.
    """

    def __init__(
        self,
        index_path: Path = BM25_INDEX_PATH,
    ) -> None:
        self.index_path = index_path
        self.records: list[dict[str, Any]] = []
        self._bm25: BM25Okapi | None = None
    #  class fucntion run with obj initalisation
        self._load()
        self._rebuild()

    def _load(self) -> None:
        """Load indexed chunk records from local JSON, if available."""
        if not self.index_path.exists():
            self.records = []
            return

        try:
            with self.index_path.open(
                "r",
                encoding="utf-8",
            ) as index_file:
                data = json.load(index_file)

            self.records = data if isinstance(data, list) else []

        except (json.JSONDecodeError, OSError):
            # Do not stop the API because of a damaged local cache.
            # A future ingestion will rebuild the local index.
            self.records = []

    def _save(self) -> None:
        """Save the BM25 source records safely."""
        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self.index_path.with_suffix(
            ".tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as index_file:
            json.dump(
                self.records,
                index_file,
                ensure_ascii=False,
            )

        temporary_path.replace(self.index_path)

    def _rebuild(self) -> None:
        """
        Rebuild the in-memory BM25 scoring object.

        The JSON file stores text and metadata; BM25 scores are rebuilt
        quickly when the service starts or documents are added.
        """
        tokenized_corpus = [
            tokenize(record["content"])
            for record in self.records
        ]

        self._bm25 = (
            BM25Okapi(tokenized_corpus)
            if tokenized_corpus
            else None
        )

    def add_documents(
        self,
        documents: list[Document],
    ) -> dict[str, int]:
        """
        Add only unseen chunks to the BM25 index.

        Chunks use the same stable ID as Chroma, so both engines refer
        to the same document chunk during RRF fusion.
        """
        existing_ids = {
            record["chunk_id"]
            for record in self.records
        }

        new_records: list[dict[str, Any]] = []

        for document in documents:
            chunk_id = build_chunk_id(document)

            if chunk_id in existing_ids:
                continue

            new_records.append(
                {
                    "chunk_id": chunk_id,
                    "content": document.page_content,
                    "metadata": dict(document.metadata),
                }
            )

        if new_records:
            self.records.extend(new_records)
            self._save()
            self._rebuild()

        return {
            "received": len(documents),
            "indexed": len(new_records),
            "skipped": len(documents) - len(new_records),
        }

    def search(
        self,
        query: str,
        k: int = 20,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return top sparse-search candidates.

        `metadata_filter` can later restrict results to one user's
        document collection, one PDF, or one reaction class.
        """
        if not self._bm25 or not query.strip():
            return []

        query_tokens = tokenize(query)

        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        candidates: list[dict[str, Any]] = []

        for record, score in zip(self.records, scores):
            if score <= 0:
                continue

            if not _matches_metadata_filter(
                record["metadata"],
                metadata_filter,
            ):
                continue

            candidates.append(
                {
                    "chunk_id": record["chunk_id"],
                    "content": record["content"],
                    "metadata": record["metadata"],
                    "bm25_score": float(score),
                }
            )

        candidates.sort(
            key=lambda candidate: candidate["bm25_score"],
            reverse=True,
        )

        top_candidates = candidates[:k]

        for rank, candidate in enumerate(
            top_candidates,
            start=1,
        ):
            candidate["rank"] = rank

        return top_candidates

    def document_count(self) -> int:
        """Return the number of indexed chunks."""
        return len(self.records)


bm25_index = LocalBM25Index()


def add_documents(
    documents: list[Document],
) -> dict[str, int]:
    """Add chunks to the persistent local BM25 index."""
    return bm25_index.add_documents(documents)


def sparse_search(
    query: str,
    k: int = 20,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run BM25 sparse/keyword retrieval."""
    return bm25_index.search(
        query=query,
        k=k,
        metadata_filter=metadata_filter,
    )
    
