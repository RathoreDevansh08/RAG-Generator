import re

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever

from rag_generator.config import Settings


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError("Name must contain at least one letter or digit")
    if len(slug) < 3:
        slug = f"{slug}-set"
    return slug[:63].rstrip("-")


def get_embeddings(settings: Settings) -> Embeddings:
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=settings.embedding_model)


class DocumentStore:
    def __init__(self, persist_dir: str, embeddings: Embeddings):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embeddings = embeddings

    def list_collections(self) -> list[str]:
        return sorted(getattr(c, "name", c) for c in self._client.list_collections())

    def _vectorstore(self, collection: str) -> Chroma:
        return Chroma(
            client=self._client,
            collection_name=collection,
            embedding_function=self._embeddings,
        )

    def add_documents(self, collection: str, docs: list[Document]) -> int:
        if not docs:
            return 0
        raw = self._client.get_or_create_collection(collection)
        existing = set(raw.get(ids=[d.metadata["chunk_id"] for d in docs])["ids"])
        seen = set(existing)
        new = []
        for d in docs:
            cid = d.metadata["chunk_id"]
            if cid not in seen:
                seen.add(cid)
                new.append(d)
        if new:
            self._vectorstore(collection).add_documents(
                new, ids=[d.metadata["chunk_id"] for d in new]
            )
        return len(new)

    def count(self, collection: str) -> int:
        return self._client.get_or_create_collection(collection).count()

    def list_sources(self, collection: str) -> dict[str, int]:
        raw = self._client.get_or_create_collection(collection)
        sources: dict[str, int] = {}
        for meta in raw.get(include=["metadatas"])["metadatas"] or []:
            src = (meta or {}).get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        return sources

    def delete_collection(self, collection: str) -> None:
        self._client.delete_collection(collection)

    def get_retriever(self, collection: str, k: int) -> BaseRetriever:
        return self._vectorstore(collection).as_retriever(search_kwargs={"k": k})
