from tools.retrieval.RAG_tool import ingest_pdf
from utils.schema import ReactionState


def pdf_upload(state: ReactionState) -> dict:
    """Ingest each uploaded PDF into the Chroma and BM25 indexes."""
    documents = state.get("uploaded_docs") or []

    if not documents:
        return {
            "pdf_ingested": False,
            "external_doc_available": False,
            "ingestion_results": [],
        }

    ingestion_results: list[dict] = []
    warnings = list(state.get("warnings", []))

    for pdf_path in documents:
        try:
            result = ingest_pdf(pdf_path)
            ingestion_results.append(
                {
                    "path": pdf_path,
                    "success": True,
                    **result,
                }
            )

        except Exception as error:
            ingestion_results.append(
                {
                    "path": pdf_path,
                    "success": False,
                    "error": str(error),
                }
            )
            warnings.append(
                f"Could not ingest '{pdf_path}': {error}"
            )

    successful_ingestions = [
        result
        for result in ingestion_results
        if result["success"]
    ]

    return {
        "pdf_ingested": bool(successful_ingestions),
        "external_doc_available": bool(successful_ingestions),
        "ingestion_results": ingestion_results,
        "document_ids": [
            result["document_id"]
            for result in successful_ingestions
            if result.get("document_id")
        ],
        "warnings": warnings,
    }
