import pytest

from rag_generator.config import Settings, get_settings

ENV_VARS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "CHROMA_DIR",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "TOP_K",
)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)  # no .env file here
    return monkeypatch


def test_defaults_target_groq_gpt_oss(clean_env):
    s = get_settings()
    assert s.llm_base_url == "https://api.groq.com/openai/v1"
    assert s.llm_model == "openai/gpt-oss-20b"
    assert s.llm_api_key == ""
    assert s.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert s.chroma_dir == "data/chroma"
    assert (s.chunk_size, s.chunk_overlap, s.top_k) == (1000, 150, 4)


def test_env_overrides_every_field(clean_env):
    values = {
        "LLM_BASE_URL": "http://localhost:11434/v1",
        "LLM_API_KEY": "k",
        "LLM_MODEL": "gpt-oss:20b",
        "EMBEDDING_MODEL": "m",
        "CHROMA_DIR": "x/y",
        "CHUNK_SIZE": "500",
        "CHUNK_OVERLAP": "50",
        "TOP_K": "8",
    }
    for k, v in values.items():
        clean_env.setenv(k, v)
    s = get_settings()
    assert s == Settings("http://localhost:11434/v1", "k", "gpt-oss:20b", "m", "x/y", 500, 50, 8)


def test_dotenv_file_is_read(clean_env, tmp_path):
    (tmp_path / ".env").write_text("LLM_MODEL=from-dotenv\nTOP_K=2\n")
    s = get_settings()
    assert s.llm_model == "from-dotenv"
    assert s.top_k == 2


def test_invalid_int_raises(clean_env):
    clean_env.setenv("TOP_K", "many")
    with pytest.raises(ValueError):
        get_settings()


def test_settings_is_immutable():
    with pytest.raises(AttributeError):
        Settings().top_k = 1  # type: ignore[misc]
