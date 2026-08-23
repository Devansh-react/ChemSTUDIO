from __future__ import annotations

from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Character counts. Tune later through evaluation.
CHUNK_SIZE = 1_200
CHUNK_OVERLAP = 150
CHUNKING_VERSION = "page-aware-v1"


def split_pages_into_sections(
    documents: Iterable[Document],
) -> list[Document]:
    """
    Treat each PDF page as one section.

    No heading detection is used because uploaded chemistry PDFs may be
    unstructured paragraphs, bullet points, reaction notes, or tables.
    """
    page_sections: list[Document] = []

    for document in documents:
        page_text = document.page_content.strip()

        if not page_text:
            continue

        metadata = dict(document.metadata)

        source = str(
            metadata.get("source")
            or metadata.get("pdf_name")
            or "unknown_source"
        )

        page_sections.append(
            Document(
                page_content=page_text,
                metadata={
                    "source": source,
                    "pdf_name": Path(source).name,
                    "page": int(metadata.get("page", 0)),
                },
            )
        )

    return page_sections


def split_documents(
    documents: Iterable[Document],
) -> list[Document]:
    """
    Split PDF pages into retrieval chunks.

    Each chunk keeps its original PDF and page metadata, so retrieved
    evidence can always be cited correctly.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "; ",
            ", ",
            " ",
        ],
    )

    page_sections = split_pages_into_sections(documents)

    chunks: list[Document] = []
    global_chunk_index = 0

    for page_section in page_sections:
        page_chunks = splitter.split_documents([page_section])

        for page_chunk_index, chunk in enumerate(page_chunks):
            chunk.metadata["chunk_index"] = global_chunk_index
            chunk.metadata["chunk_index_in_page"] = page_chunk_index
            chunk.metadata["chunk_char_count"] = len(chunk.page_content)
            chunk.metadata["chunking_version"] = CHUNKING_VERSION
            chunks.append(chunk)
            global_chunk_index += 1

    return chunks