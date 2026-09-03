import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY")
    QDRANT_URL = os.getenv("QDRANT_CLUSTER_ENDPOINT")
    QDRANT_COLLECTION = "enterprise_rag"

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = "llama2-70b-chat-hf"
    GROQ_FALLBACK_API_KEY: str = os.getenv("GROQ_FALLBACK_API_KEY")
    
settings = Settings()




    