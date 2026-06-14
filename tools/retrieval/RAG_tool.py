#  exteral data source to be given to Model  in ordere to predict the chemical reaction 

from pdf_loader import load_pdf
from text_splitter import split_documents
from chroma_tool import add_documents, similarity_score_threshold , mmr_search

def ingest_pdf(pdf_path:str):
    try:
        docs = load_pdf(pdf_path)
        if not docs:
            return None
        
        chunks = split_documents(docs)
        for doc in chunks:
            doc.metadata["pdf_name"] = pdf_path
            
        add_documents(chunks)
        return chunks
    
    except Exception as e:
        print(f"Error splitting documents: {e}")
        return None
    

def retrieve_context(query,k=5):
    return similarity_score_threshold(query,k)

def retrieve_context_mmr(query):
    return mmr_search(query,k=5)

#  later add on the logic on how to use both similarity and mmr accordinly 
def hybrid_retrieve_context(query,k=5):
    pass