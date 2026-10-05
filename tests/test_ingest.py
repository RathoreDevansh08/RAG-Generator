from langchain_core.documents import Document

from rag_generator.ingest import ingest_files, split_documents


def test_split_long_text_has_chunk_ids(settings):
    doc = Document(page_content="word " * 200, metadata={"source": "a.txt"})
    chunks = split_documents([doc], settings)
    assert len(chunks) > 1
    ids = [c.metadata["chunk_id"] for c in chunks]
    assert all(ids) and len(set(ids)) == len(ids)


def test_tabular_short_not_split(settings):
    text = "a,b\n" + "1,2\n" * 30  # < 200 chars
    assert len(text) <= settings.chunk_size
    doc = Document(page_content=text, metadata={"source": "t.csv", "tabular": True})
    assert len(split_documents([doc], settings)) == 1


def test_none_metadata_dropped(settings):
    doc = Document(
        page_content="hello", metadata={"source": "a.txt", "page": None, "obj": [1]}
    )
    (chunk,) = split_documents([doc], settings)
    assert "page" not in chunk.metadata
    assert "obj" not in chunk.metadata
    assert chunk.metadata["source"] == "a.txt"


def test_ingest_files_txt(store, settings, tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello world. " * 100, encoding="utf-8")
    result = ingest_files(store, "col", [(p, "note.txt")], settings)
    assert result["note.txt"] > 0
    assert store.count("col") == result["note.txt"]
