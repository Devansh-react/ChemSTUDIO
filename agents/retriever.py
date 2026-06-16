
from utils.schemas_chat import ReactionState 
from tools.retrieval.RAG_tool import ingest_pdf,retrieve_context,retrieve_context_mmr


def retriever_agent(state:ReactionState):
    if not state.get("pdf_injested",False):
        return {
            "external_doc_available":False,
            "retrieved_context":[]
        }
    
    query = f"""
    Reaction Prediction

    Reactant:
    {state.get(
        "canonical_smiles",
        state["smiles"]
    )}

    Conditions:
    {state["conditions"]}
    """
    retrieved_context_mmr = retrieve_context_mmr(query)
    
    content = []
    
    for doc in retrieved_context_mmr:
        content.append(
        {
            "content":
                doc.page_content,

            "source":
                doc.metadata.get(
                    "pdf_name"
                ),

            "page":
                doc.metadata.get(
                    "page"
                ),

            "metadata":
                doc.metadata
        }
        )
    return {
        "external_doc_available":True,
        "retrieved_context" : content
    }
    
    
    
    
    
    
    