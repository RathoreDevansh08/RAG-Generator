import hashlib
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_generator.config import Settings
from rag_generator.loaders import load_file
from rag_generator.store import DocumentStore


def split_documents(docs: list[Document], settings: Settings) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
    )
    chunks: list[Document] = []
    for doc in docs:
        if doc.metadata.get("tabular") and len(doc.page_content) <= settings.chunk_size:
            chunks.append(doc)
        else:
            chunks.extend(splitter.split_documents([doc]))

    result: list[Document] = []
    seen: set[str] = set()
    for chunk in chunks:
        meta = {
            k: v
            for k, v in chunk.metadata.items()
            if v is not None and isinstance(v, (str, int, float, bool))
        }
        source = str(meta.get("source", ""))
        cid = hashlib.sha256(
            (source + "\x00" + chunk.page_content).encode()
        ).hexdigest()[:32]
        if cid in seen:
            continue
        seen.add(cid)
        meta["chunk_id"] = cid
        result.append(Document(page_content=chunk.page_content, metadata=meta))
    return result


def ingest_files(
    store: DocumentStore,
    collection: str,
    files: list[tuple[Path, str]],
    settings: Settings,
) -> dict[str, int]:
    result: dict[str, int] = {}
    for path, display_name in files:
        chunks = split_documents(load_file(path, display_name), settings)
        store.add_documents(collection, chunks)
        result[display_name] = len(chunks)
    return result
