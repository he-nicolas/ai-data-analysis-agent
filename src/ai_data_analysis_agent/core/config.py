import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
    GUARD_LLM_MODEL: str = os.environ.get("GUARD_LLM_MODEL", "llama-3.1-8b-instant") 

    EXAMPLE_DB = os.getenv("EXAMPLE_DB")
    EXAMPLE_FILE = os.getenv("EXAMPLE_FILE")

    UPLOAD_DIR =os.getenv("UPLOAD_DIR")