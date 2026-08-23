from __future__ import annotations

import hashlib
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

def calculate_file_checksum(
    pdf_path: str | Path,
    block_size: int = 1_048_576,
) -> str:
    """
    Return a SHA-256 checksum for a PDF.

    The checksum changes if the file content changes. It is used for
    ingestion caching and to identify one document reliably.
    """
    hasher = hashlib.sha256()

    with Path(pdf_path).open("rb") as pdf_file:
        while block := pdf_file.read(block_size):
            hasher.update(block)

    return hasher.hexdigest()

def pdf_loader(pdf_path:str | Path):
    """
    Load one PDF and attach consistent metadata to every page.

    Raises:
        FileNotFoundError: when the supplied path does not exist.
        ValueError: when the file is not a PDF or has no readable text.
    """
    resolve_path = Path(pdf_path).expanduser().resolve()
    
    if not resolve_path:
        raise FileNotFoundError(
            f"PDF file was not found: {resolve_path}"
        )
    
    if resolve_path.suffix.lower()!="pdf":
        raise ValueError(
            f"Only PDF files are supported: {resolve_path.name}"
        )
    
    document_checksum = calculate_file_checksum(resolve_path)
    
    loader = PyPDFLoader(resolve_path)
    pages = loader.load()
    
    if not  pages:
        raise ValueError(
            f"No readable text was extracted from: {resolve_path.name}"
        )
    
    total_len = len(pages)
    
    for page_index, document in enumerate(pages):
        document.metadata.update(
            {
                "source": str(resolve_path),
                "pdf_name": resolve_path.name,
                "document_id": document_checksum,
                "document_checksum": document_checksum,
                "page": int(
                    document.metadata.get("page", page_index)
                ),
                "total_pages": total_len,
            }
        )

    return pages