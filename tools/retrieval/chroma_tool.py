from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
from langchain_chroma import Chroma
import os

load_dotenv()

model= os.getenv(
    "Embedding_MODEL"
)

embeddings = HuggingFaceEmbeddings(model_name=model)

db = Chroma(
    persist_directory="database/chroma",
    embedding_function=embeddings
)


def add_document(documents):
    db.add_documents(documents)
    
    
def similarity_score_threshold(
        query:str,
        k:int=5
):

    retriever = db.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "score_threshold":0.2,
            "k":k
        }
    )

    return retriever.invoke(query)


def mmr_search(
        query:str,
        k:int=5
):

    retriever = db.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k":k,
            "fetch_k":20,
            "lambda_mult":0.5
        }
    )

    return retriever.invoke(query)
