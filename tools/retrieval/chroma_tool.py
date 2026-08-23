from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

model= os.getenv(
    "Embedding_MODEL"
)
COLLECTION = os.environ["CHROMA_COLLECTION_NAME"]

embeddings = HuggingFaceEmbeddings(model_name=model)

DIRECTORY = os.getenv("CHROMA_PRESIST_DIRECTORY")

db = Chroma(
    collection_name= COLLECTION,
    persist_directory = DIRECTORY,
    embedding_function=embeddings
)
def normalise_text(text:str)->str:
    return "".join(text.split())

# Creates a unique permanent ID for every chunk.
def build_chunk_id(document:Document):
    """
    Create a stable ID for one chunk.

    Same source document + page + chunk index + normalized text
    creates the same ID, so re-ingesting an unchanged PDF does not
    create duplicate vectors.
    
    """
    metadata = document.metadata
    
    source = str(
        metadata.get("source") or metadata.get("pdf_name") or " unkown_source"
    )
    
    page = str(metadata.get("page") or "unkonwn_page")
    content = normalise_text(document.page_content)
    chunk_index = str(metadata.get("chunk_index")or "unkown_chunk")
    
    raw_key = f"{source}|{page}|{content}|{chunk_index}"
    
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

# Prepares every chunk before saving it in Chroma.
def prepare_document(document:Document)->Document:
    """
    Normalize a LangChain document and ensure retrieval metadata exists.

    Chroma metadata must use scalar values only. Do not store dicts/lists here.
    """
    metadata = dict(document.metadata)
    source = str(metadata.get("source") or metadata.get("pdf_name") or " unkown_source")
    
    metadata["source"] = source
    metadata['page'] = int(metadata.get("page",0))
    metadata["pdf_name"] = Path(source).name
    metadata["chunk_index"] = int(metadata.get("chunk_index",0))
    metadata["embedding_model"] = model
    metadata["content_hash"] = hashlib.sha256(document.page_content.encode("utf-8")).hexdigest()
    
    return Document(
        page_content=normalise_text(document.page_content),
        metadata = metadata
    )

# Checks whether chunks already exist in Chroma before adding them.
def _chunks_not_already_indexed(document :Iterable[Document]):
    """
    Return only new chunks.

    This is the first indexing cache: Chroma itself is used to determine
    whether a stable chunk ID has been indexed already.
    """ 
    prepared_document = [prp_docs for prp_docs in document]
    chunk_ids = [build_chunk_id(doc) for doc in document]
    
    existing_ids = db.get(ids=chunk_ids,include=[])
    exisiting_id_set = set(existing_ids.get("ids",[]))
    
    new_document:list[Document]=[]
    new_chunk:list[str] = []
    
    for doc, id  in zip(prepared_document,chunk_ids):
        if id not in exisiting_id_set:
            new_document.append(doc)
            new_chunk.append(id)
        
    
    return new_document, new_chunk

# Checks whether chunks already exist in Chroma before adding them.
def add_document(documents:list[Document]):
    new_docs, new_id = _chunks_not_already_indexed(documents)
    
    if new_docs:
        db.add_documents(
            documents=new_docs,
            ids = new_id
        )
    
    return {
        "recieved":len(documents),
        "index":len(new_docs),
        "skipped":len(documents)-len(new_docs)
    }

# Performs semantic/vector search.
def dense_search(query: str,k:int = 20,  metadata_filter : dict[str,Any]| None = None):
    """
    Return dense-search candidates with distance values.

    Smaller Chroma distance values indicate closer semantic matches.
    RRF will later combine only rankings, so no score normalization is needed.
    """
    results = db.similarity_search_with_score(
        query=query,
        k=k,
        filter=metadata_filter
    )
    #  return the doc and score in list 
    
    candidates : list[dict[str,Any]] = []
    
    for rank,(documents, score) in enumerate(results,start=1):
        candidates.append(
            {
                "chunk_id": build_chunk_id(documents),
                "content":documents.page_content,
                "metadata": documents.metadata,
                "dense_distance": score,
                "rank": rank,
            }
        )

    return candidates

#previous 
def similarity_score_threshold(
    query: str,
    k: int = 5,
    score_threshold: float = 0.2,
):
    """
    Existing API retained temporarily.

    Note: this remains dense-only. Hybrid retrieval will replace this
    call in RAG_tool.py in a later step.
    """
    retriever = db.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "score_threshold": score_threshold,
            "k": k,
        },
    )
    return retriever.invoke(query)

def mmr_search(
    query: str,
    k: int = 5,
    fetch_k: int = 20,
    lambda_mult: float = 0.5,
):
    """Existing MMR API retained while hybrid retrieval is introduced."""
    retriever = db.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k,
            "fetch_k": fetch_k,
            "lambda_mult": lambda_mult,
        },
    )
    return retriever.invoke(query)


