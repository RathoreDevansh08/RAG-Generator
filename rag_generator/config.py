import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-20b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_dir: str = "data/chroma"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 4


def get_settings() -> Settings:
    load_dotenv(find_dotenv(usecwd=True))
    defaults = Settings()
    return Settings(
        llm_base_url=os.getenv("LLM_BASE_URL", defaults.llm_base_url),
        llm_api_key=os.getenv("LLM_API_KEY", defaults.llm_api_key),
        llm_model=os.getenv("LLM_MODEL", defaults.llm_model),
        embedding_model=os.getenv("EMBEDDING_MODEL", defaults.embedding_model),
        chroma_dir=os.getenv("CHROMA_DIR", defaults.chroma_dir),
        chunk_size=int(os.getenv("CHUNK_SIZE", defaults.chunk_size)),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", defaults.chunk_overlap)),
        top_k=int(os.getenv("TOP_K", defaults.top_k)),
    )
