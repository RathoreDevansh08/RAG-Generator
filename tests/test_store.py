import pytest
from langchain_core.documents import Document

from rag_generator.store import slugify


def make_docs(source, n, prefix="doc"):
    return [
        Document(
            page_content=f"{prefix} content number {i} for {source}",
            metadata={"source": source, "chunk_id": f"{prefix}-{source}-{i}"},
        )
        for i in range(n)
    ]


def test_slugify_basic():
    assert slugify("My Docs!") == "my-docs"
    assert slugify("  Hello___World  ") == "hello-world"


def test_slugify_short_padded():
    s = slugify("ab")
    assert s == "ab-set"
    assert len(s) >= 3


def test_slugify_long_trimmed():
    s = slugify("a" * 100)
    assert len(s) <= 63
    assert not s.endswith("-")


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        slugify("!!!")


def test_add_and_count(store):
    assert store.add_documents("c1", make_docs("a.txt", 3)) == 3
    assert store.count("c1") == 3


def test_readd_is_idempotent(store):
    docs = make_docs("a.txt", 3)
    store.add_documents("c1", docs)
    assert store.add_documents("c1", docs) == 0
    assert store.count("c1") == 3


def test_list_sources(store):
    store.add_documents("c1", make_docs("a.txt", 2) + make_docs("b.txt", 3))
    assert store.list_sources("c1") == {"a.txt": 2, "b.txt": 3}


def test_delete_collection(store):
    store.add_documents("c1", make_docs("a.txt", 1))
    assert "c1" in store.list_collections()
    store.delete_collection("c1")
    assert "c1" not in store.list_collections()


def test_collections_isolated(store):
    store.add_documents("ca", make_docs("a.txt", 3, prefix="alpha"))
    store.add_documents("cb", make_docs("b.txt", 3, prefix="beta"))
    assert store.list_collections() == ["ca", "cb"]
    docs = store.get_retriever("ca", 10).invoke("content")
    assert docs
    assert all(d.metadata["source"] == "a.txt" for d in docs)


def test_get_retriever_returns_docs(store):
    store.add_documents("c1", make_docs("a.txt", 5))
    docs = store.get_retriever("c1", 2).invoke("content number 1")
    assert len(docs) == 2
