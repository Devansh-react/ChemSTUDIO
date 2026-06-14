from graph.state import ReactionState
from tools.retrieval.RAG_tool import ingest_pdf


def pdf_upload(state: ReactionState):

    docs = state.get("uploaded_docs",[])

    if not docs:
        return {
            "pdf_ingested": False
        }

    try:

        for pdf in docs:
            ingest_pdf(pdf)

        return {
            "pdf_ingested": True
        }

    except Exception as e:

        return {
            "pdf_ingested": False,
            "warnings": [str(e)]
        }