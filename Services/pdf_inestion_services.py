from tools.retrieval.RAG_tool import ingest_pdf
from utils.schema import ReactionState
from database.service import DatabaseService
from database.database import Database
from uuid import UUID
import os
import hashlib
import asyncio

# Initialize DB service (module-level singleton)
db = Database("postgresql+psycopg://chemstudio:chemstudio_dev@localhost:5432/chem_process_studio")
db.initialize()
db_service = DatabaseService(db)


def compute_sha256(filepath: str) -> str:
    """Compute SHA256 checksum of file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def pdf_upload(state: ReactionState, user_id: str = None) -> dict:
    """Ingest each uploaded PDF into the Chroma and BM25 indexes AND persist to PostgreSQL."""
    documents = state.get("uploaded_docs") or []

    if not documents:
        return {
            "pdf_ingested": False,
            "external_doc_available": False,
            "ingestion_results": [],
        }

    ingestion_results: list[dict] = []
    warnings = list(state.get("warnings", []))

    # Parse user_id
    user_uuid = None
    if user_id:
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            pass

    for pdf_path in documents:
        doc = None
        try:
            # Compute checksum BEFORE ingestion
            checksum = compute_sha256(pdf_path)
            filename = os.path.basename(pdf_path)
            file_size = os.path.getsize(pdf_path)

            # 1. Create document record in DB (status: pending)
            if user_uuid:
                doc = asyncio.run(db_service.create_document(
                    user_id=user_uuid,
                    filename=filename,
                    object_key=pdf_path,
                    file_size_bytes=file_size,
                    checksum_sha256=checksum,
                    mime_type="application/pdf"
                ))

            # 2. Run existing ingestion (Chroma + BM25)
            result = ingest_pdf(pdf_path)

            # 3. Prepare chunk data for DB
            chunks_data = []
            for chunk in result.get("chunks", []):
                chunks_data.append({
                    "chunk_id": chunk.metadata.get("chunk_id"),
                    "page_number": chunk.metadata.get("page"),
                    "chunk_index": chunk.metadata.get("chunk_index"),
                    "section_heading": chunk.metadata.get("section_heading"),
                    "char_start": chunk.metadata.get("char_start"),
                    "char_end": chunk.metadata.get("char_end"),
                    "token_count": chunk.metadata.get("chunk_char_count"),
                    "content_hash": chunk.metadata.get("content_hash"),
                })

            # 4. Store chunks in DB
            if chunks_data and doc:
                asyncio.run(db_service.create_document_chunks(doc.id, chunks_data))

            # 5. Update document status in DB
            if doc:
                asyncio.run(db_service.update_document_ingestion(
                    doc_id=doc.id,
                    status="completed",
                    chunk_count=result.get("chunks_created", 0),
                    chroma_collection=result.get("chroma", {}).get("collection", ""),
                    bm25_indexed=True
                ))

            ingestion_results.append({
                "path": pdf_path,
                "success": True,
                "document_id": str(doc.id) if doc else None,
                **result,
            })

        except Exception as error:
            # Update DB with failure if doc was created
            if doc:
                asyncio.run(db_service.update_document_ingestion(
                    doc_id=doc.id,
                    status="failed",
                    error=str(error)
                ))

            ingestion_results.append({
                "path": pdf_path,
                "success": False,
                "error": str(error),
            })
            warnings.append(f"Could not ingest '{pdf_path}': {error}")

    successful_ingestions = [r for r in ingestion_results if r["success"]]

    return {
        "pdf_ingested": bool(successful_ingestions),
        "external_doc_available": bool(successful_ingestions),
        "ingestion_results": ingestion_results,
        "document_ids": [r["document_id"] for r in successful_ingestions if r.get("document_id")],
        "warnings": warnings,
    }