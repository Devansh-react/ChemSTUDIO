from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

env = load_dotenv()

def split_documents(documents):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " "
        ]
    )

    return splitter.split_documents(
        documents
    )

        
