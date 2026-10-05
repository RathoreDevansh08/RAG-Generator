import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from rag_generator.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        chroma_dir=str(tmp_path / "chroma"),
        chunk_size=200,
        chunk_overlap=20,
        llm_api_key="test-key",
    )


@pytest.fixture
def fake_embeddings() -> DeterministicFakeEmbedding:
    return DeterministicFakeEmbedding(size=64)


@pytest.fixture
def store(settings: Settings, fake_embeddings: DeterministicFakeEmbedding):
    from rag_generator.store import DocumentStore

    return DocumentStore(settings.chroma_dir, fake_embeddings)
