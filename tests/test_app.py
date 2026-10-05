from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from streamlit.testing.v1 import AppTest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setattr(
        "rag_generator.store.get_embeddings",
        lambda s: DeterministicFakeEmbedding(size=64),
    )
    return AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=30)


def test_app_runs(app):
    app.run()
    assert not app.exception


def test_info_when_no_sets(app):
    app.run()
    assert any("Create a document set" in i.value for i in app.info)


def test_warning_when_no_key(app):
    app.session_state["active"] = "demo"
    app.run()
    assert any("LLM_API_KEY" in w.value for w in app.warning)
