"""Integration tests: loaders -> ingest -> store -> retriever -> chain, all offline."""

from pathlib import Path

import pandas as pd
import pytest
from langchain_core.language_models import FakeListChatModel

from rag_generator.chain import NOT_FOUND_MESSAGE, answer_question
from rag_generator.ingest import ingest_files, split_documents
from rag_generator.loaders import EmptyDocumentError, UnsupportedFileError, load_file
from rag_generator.store import DocumentStore


class ExplodingLLM(FakeListChatModel):
    def _call(self, *args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("LLM must not be called")


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_end_to_end_answer_cites_ingested_file(store, settings, tmp_path):
    f = write(tmp_path, "policy.txt", "Employees get 25 vacation days per year.")
    ingest_files(store, "hr-docs", [(f, "policy.txt")], settings)
    llm = FakeListChatModel(responses=["25 days [policy.txt]"])
    ans = answer_question("How many vacation days?", store.get_retriever("hr-docs", 4), llm)
    assert ans.text == "25 days [policy.txt]"
    assert [s.source for s in ans.sources] == ["policy.txt"]
    assert ans.sources[0].snippet.startswith("Employees get 25")


def test_empty_collection_short_circuits(store, settings):
    ans = answer_question(
        "anything", store.get_retriever("empty-set", 4), ExplodingLLM(responses=[])
    )
    assert ans.text == NOT_FOUND_MESSAGE
    assert ans.sources == []


def test_model_not_found_reply_has_no_sources(store, settings, tmp_path):
    f = write(tmp_path, "a.txt", "Cats sleep a lot.")
    ingest_files(store, "pets", [(f, "a.txt")], settings)
    llm = FakeListChatModel(responses=[f"Sorry. {NOT_FOUND_MESSAGE}"])
    ans = answer_question("Stock price?", store.get_retriever("pets", 4), llm)
    assert ans == type(ans)(NOT_FOUND_MESSAGE, [])


def test_document_sets_are_isolated_through_chain(store, settings, tmp_path):
    a = write(tmp_path, "a.txt", "Set A secret is apple.")
    b = write(tmp_path, "b.txt", "Set B secret is banana.")
    ingest_files(store, "set-a", [(a, "a.txt")], settings)
    ingest_files(store, "set-b", [(b, "b.txt")], settings)
    llm = FakeListChatModel(responses=["x"])
    ans = answer_question("secret?", store.get_retriever("set-b", 10), llm)
    assert {s.source for s in ans.sources} == {"b.txt"}


def test_reingesting_same_file_is_idempotent(store, settings, tmp_path):
    f = write(tmp_path, "doc.md", "# Title\n\n" + "Paragraph text. " * 60)
    first = ingest_files(store, "docs", [(f, "doc.md")], settings)
    count = store.count("docs")
    second = ingest_files(store, "docs", [(f, "doc.md")], settings)
    assert first == second
    assert store.count("docs") == count == first["doc.md"]
    assert first["doc.md"] > 1  # chunk_size=200 forces splitting


def test_same_text_different_files_are_distinct_chunks(store, settings, tmp_path):
    a = write(tmp_path, "a.txt", "Shared sentence.")
    b = write(tmp_path, "b.txt", "Shared sentence.")
    ingest_files(store, "dup", [(a, "a.txt"), (b, "b.txt")], settings)
    assert store.list_sources("dup") == {"a.txt": 1, "b.txt": 1}


def test_index_survives_restart(settings, fake_embeddings, tmp_path):
    f = write(tmp_path, "keep.txt", "Persistent fact.")
    ingest_files(
        DocumentStore(settings.chroma_dir, fake_embeddings), "keep", [(f, "keep.txt")], settings
    )
    reopened = DocumentStore(settings.chroma_dir, fake_embeddings)
    assert "keep" in reopened.list_collections()
    assert reopened.count("keep") == 1


def test_csv_rows_cited_by_row(store, settings, tmp_path):
    p = tmp_path / "people.csv"
    pd.DataFrame({"name": ["Ann", "Bob"], "city": ["Oslo", "Rome"]}).to_csv(p, index=False)
    counts = ingest_files(store, "people", [(p, "people.csv")], settings)
    assert counts == {"people.csv": 2}
    ans = answer_question(
        "Bob?", store.get_retriever("people", 2), FakeListChatModel(responses=["Rome"])
    )
    assert sorted(s.row for s in ans.sources) == [1, 2]
    assert all(s.page is None for s in ans.sources)


def test_pdf_pages_cited_by_page(store, settings, tmp_path):
    from fpdf import FPDF

    p = tmp_path / "r.pdf"
    pdf = FPDF()
    for text in ("First page facts", "Second page facts"):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(text=text)
    pdf.output(str(p))
    ingest_files(store, "rep", [(p, "r.pdf")], settings)
    ans = answer_question(
        "facts", store.get_retriever("rep", 2), FakeListChatModel(responses=["ok"])
    )
    assert sorted(s.page for s in ans.sources) == [1, 2]


def test_ingest_unsupported_file_raises_and_stores_nothing(store, settings, tmp_path):
    f = write(tmp_path, "x.exe", "MZ")
    with pytest.raises(UnsupportedFileError):
        ingest_files(store, "bad", [(f, "x.exe")], settings)
    assert store.count("bad") == 0


def test_ingest_empty_file_raises(store, settings, tmp_path):
    f = write(tmp_path, "blank.txt", "   \n")
    with pytest.raises(EmptyDocumentError):
        ingest_files(store, "bad", [(f, "blank.txt")], settings)


def test_chunk_ids_are_deterministic(settings, tmp_path):
    f = write(tmp_path, "d.txt", "Some words. " * 50)
    ids1 = [c.metadata["chunk_id"] for c in split_documents(load_file(f, "d.txt"), settings)]
    ids2 = [c.metadata["chunk_id"] for c in split_documents(load_file(f, "d.txt"), settings)]
    assert ids1 == ids2
    assert len(set(ids1)) == len(ids1)
    assert all(len(i) == 32 for i in ids1)


def test_chunks_respect_chunk_size(settings, tmp_path):
    f = write(tmp_path, "big.txt", "word " * 2000)
    chunks = split_documents(load_file(f, "big.txt"), settings)
    assert all(len(c.page_content) <= settings.chunk_size for c in chunks)


def test_snippet_truncated_to_200_chars(store, settings, tmp_path):
    f = write(tmp_path, "long.txt", "x" * 190)
    ingest_files(store, "long", [(f, "long.txt")], settings)
    ans = answer_question("x", store.get_retriever("long", 1), FakeListChatModel(responses=["ok"]))
    assert len(ans.sources[0].snippet) <= 200


def test_top_k_limits_sources(store, settings, tmp_path):
    files = [(write(tmp_path, f"f{i}.txt", f"Fact number {i}."), f"f{i}.txt") for i in range(6)]
    ingest_files(store, "many", files, settings)
    ans = answer_question(
        "fact", store.get_retriever("many", 3), FakeListChatModel(responses=["ok"])
    )
    assert len(ans.sources) == 3
