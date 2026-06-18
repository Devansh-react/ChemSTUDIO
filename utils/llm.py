import os
import getpass
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def get_gemini_model():
    return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=1.0,  # Gemini 3.0+ defaults to 1.0
            max_tokens=None,
            timeout=None,
            max_retries=2,
            verbose=True,
    )
    


if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("")
    
def get_open_ai_model():
    return ChatOpenAI(
        model="gpt-4o",
        temperature=1.0,
        timeout=None,
        max_retries=2,
        verbose=True,
    )
    

# Example usage function
def call_llm(prompt: str):
    llm = get_gemini_model()
    return llm.invoke(prompt)