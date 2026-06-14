from langchain_community.document_loaders import PyPDFLoader

def load_pdf(pdf_path:str):
    try: 
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        return documents
    
    except Exception as e:
        print(f"Error loading PDF: {e}")
        return None
        
    
    