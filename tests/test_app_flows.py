"""Streamlit UI flows driven through AppTest with fake embeddings and a fake LLM."""

from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from streamlit.testing.v1 import AppTest

from rag_generator.store import DocumentStore


def fake_embeddings(_settings=None):
    return DeterministicFakeEmbedding(size=64)


@pytest.fixture
def env(tmp_path, monkeypatch):
    chroma = tmp_path / "chroma"
    monkeypatch.setenv("CHROMA_DIR", str(chroma))
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr("rag_generator.store.get_embeddings", fake_embeddings)
    return monkeypatch, str(chroma)


def seed(chroma_dir: str, collection: str, text: str, source: str) -> None:
    store = DocumentStore(chroma_dir, fake_embeddings())
    store.add_documents(
        collection,
        [Document(page_content=text, metadata={"source": source, "chunk_id": f"{source}-1"})],
    )


def run_app() -> AppTest:
    return AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=30).run()


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def test_existing_sets_listed_after_restart(env):
    _, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")
    seed(chroma, "beta", "B text", "b.txt")
    at = run_app()
    assert not at.exception
    assert list(at.selectbox[0].options) == ["alpha", "beta"]


def test_sidebar_lists_sources_with_chunk_counts(env):
    _, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")
    at = run_app()
    assert any("a.txt" in c.value and "1 chunks" in c.value for c in at.sidebar.caption)


def test_create_set_slugifies_and_activates(env):
    at = run_app()
    at.text_input[0].input("My Docs!")
    button(at, "Create").click()
    at.run()
    assert at.session_state["active"] == "my-docs"
    assert not at.info  # "create a set" prompt gone


def test_create_set_invalid_name_shows_error(env):
    at = run_app()
    at.text_input[0].input("!!!")
    button(at, "Create").click()
    at.run()
    assert at.error


def test_index_button_disabled_without_files(env):
    _, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")
    at = run_app()
    assert button(at, "Index documents").proto.disabled


def test_delete_requires_confirmation(env):
    _, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")
    at = run_app()
    assert button(at, "Delete document set").proto.disabled
    at.checkbox[0].check()
    at.run()
    button(at, "Delete document set").click()
    at.run()
    assert DocumentStore(chroma, fake_embeddings()).list_collections() == []


def test_chat_enabled_with_key(env):
    _, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")
    at = run_app()
    assert not at.warning
    assert not at.chat_input[0].proto.disabled


def test_chat_disabled_without_key(env):
    monkeypatch, chroma = env
    monkeypatch.setenv("LLM_API_KEY", "")
    seed(chroma, "alpha", "A text", "a.txt")
    at = run_app()
    assert at.chat_input[0].proto.disabled
    assert any("console.groq.com" in w.value for w in at.warning)


def test_question_answer_with_sources(env):
    monkeypatch, chroma = env
    seed(chroma, "alpha", "The sky is blue.", "sky.txt")
    monkeypatch.setattr(
        "rag_generator.llm.build_llm",
        lambda s: FakeListChatModel(responses=["Blue [sky.txt]"]),
    )
    at = run_app()
    at.chat_input[0].set_value("What colour is the sky?").run()
    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert "What colour is the sky?" in texts
    assert "Blue [sky.txt]" in texts
    assert any("sky.txt" in t for t in texts)  # sources expander
    history = at.session_state["history"]["alpha"]
    assert [m["role"] for m in history] == ["user", "assistant"]


def test_history_is_per_set(env):
    monkeypatch, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")
    seed(chroma, "beta", "B text", "b.txt")
    monkeypatch.setattr(
        "rag_generator.llm.build_llm", lambda s: FakeListChatModel(responses=["ans"])
    )
    at = run_app()
    at.chat_input[0].set_value("q1").run()
    at.selectbox[0].select("beta").run()
    assert at.session_state["history"].get("beta", []) == []
    assert len(at.session_state["history"]["alpha"]) == 2


def test_rate_limit_error_is_friendly(env):
    monkeypatch, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")

    def boom(*_a, **_k):
        raise RuntimeError("429 Rate limit reached")

    monkeypatch.setattr("rag_generator.chain.answer_question", boom)
    at = run_app()
    at.chat_input[0].set_value("q").run()
    assert not at.exception
    assert any("Rate limited" in e.value for e in at.error)


def test_generic_llm_error_shown(env):
    monkeypatch, chroma = env
    seed(chroma, "alpha", "A text", "a.txt")

    def boom(*_a, **_k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("rag_generator.chain.answer_question", boom)
    at = run_app()
    at.chat_input[0].set_value("q").run()
    assert any("connection refused" in e.value for e in at.error)
