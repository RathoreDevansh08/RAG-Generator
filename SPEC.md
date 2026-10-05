# Spec: RAG-Generator

## Objective

Build a Streamlit app that turns any set of documents uploaded at runtime into a question-answering (RAG) application. Every answer must be grounded in those documents.

**Users:** people who want to ask questions about their own documents, such as reports, manuals, policies or spreadsheets, without writing code. Assessment reviewers are also users: they need to run the app locally and trust that its answers come from the uploaded documents.

**User stories**

1. As a user, I upload one or more files (PDF, TXT, MD, DOCX, HTML, CSV, XLSX) and give the set a name, and the app indexes them.
2. As a user, I ask a question in a chat box and get an answer built only from my documents, with the source file (and page or row, where it applies) cited for each answer.
3. As a user, when my documents don't contain the answer, the app says so instead of guessing.
4. As a user, I switch to another document set, or create a new one, from the sidebar without restarting the app or changing code.
5. As a user, my indexed document sets are still there after I restart the app.

**Assumptions**

1. The app runs locally for a single user. It has no authentication and no multi-tenant isolation.
2. Questions are single-turn. Chat history is shown in the UI, but earlier turns are not used to rewrite follow-up questions in v1.
3. PDFs are text-based. Scanned or image-only PDFs are not OCR'd; the app warns that no text was extracted.
4. Uploaded files can be up to 50 MB each, which is the Streamlit upload limit set in config.
5. The answer language follows the question, and no translation is added.

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| UI | Streamlit (fixed) |
| RAG framework | LangChain (`langchain`, `langchain-core`, `langchain-community`, `langchain-text-splitters`) |
| LLM | **Groq free tier**, model `openai/gpt-oss-20b`, called through `langchain-openai`'s `ChatOpenAI` with `base_url=https://api.groq.com/openai/v1` |
| Embeddings | Local `sentence-transformers/all-MiniLM-L6-v2` via `langchain-huggingface` (no API key, runs on CPU) |
| Vector store | ChromaDB persisted to disk via `langchain-chroma` |
| Loaders | `pypdf` (PDF), `docx2txt` (DOCX), `beautifulsoup4` (HTML), LangChain `CSVLoader`, `pandas` + `openpyxl` (XLSX/XLS) |
| Config | `python-dotenv` reading `.env` |
| Tooling | `pytest`, `pytest-cov`, `ruff` |

The LLM is set entirely through env vars (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`). Switching to OpenRouter, Ollama or paid OpenAI needs no code change.

## Commands

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env            # then set LLM_API_KEY (free key from console.groq.com)

# Run
streamlit run app.py

# Test
pytest -q
pytest --cov=rag_generator --cov-report=term-missing

# Lint / format
ruff check . --fix
ruff format .
```

## Project Structure

```
app.py                      → Streamlit entry point (UI only, no RAG logic)
rag_generator/
  __init__.py
  config.py                 → Settings dataclass loaded from env (.env); defaults for chunk size, top_k, paths, model
  loaders.py                → File → list[Document]; one loader per extension, registered in a dict
  ingest.py                 → Split documents into chunks, attach metadata, add to a collection
  store.py                  → Chroma client wrapper: list/create/delete collections, get retriever
  llm.py                    → Build ChatOpenAI from Settings
  chain.py                  → Grounded QA chain: retrieve → prompt → LLM → answer + sources
  prompts.py                → System/user prompt templates
tests/
  conftest.py               → Fixtures: fake embeddings, fake chat model, tmp Chroma dir
  fixtures/                 → Tiny sample.pdf, sample.docx, sample.html, sample.csv, sample.xlsx, sample.md
  test_loaders.py
  test_ingest.py
  test_store.py
  test_chain.py
  test_app.py               → Streamlit AppTest smoke tests
data/chroma/                → Persisted vector store (git-ignored)
.env.example                → LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, EMBEDDING_MODEL, CHROMA_DIR
requirements.txt / requirements-dev.txt
README.md / SPEC.md
```

**Layering rule:** `app.py` imports only from `rag_generator`. `rag_generator` never imports `streamlit`. This keeps all the logic testable without the UI.

## Code Style

- Format and lint with ruff (line length 100). Type hints on every public function. Use `snake_case` for functions and modules and `PascalCase` for classes.
- Keep functions small and pure where possible. Dependencies such as embeddings, the LLM and the Chroma directory are passed in rather than created inside functions, so tests can swap in fakes.
- No bare `except`. Unsupported or unreadable files raise `UnsupportedFileError` or `EmptyDocumentError`, and the UI shows them as `st.error`.
- Collection names are slugified (`[a-z0-9-]`, 3–63 chars) to meet Chroma's naming rules.

```python
# rag_generator/loaders.py
from pathlib import Path
from typing import Callable

from langchain_core.documents import Document

Loader = Callable[[Path], list[Document]]
_LOADERS: dict[str, Loader] = {}


class UnsupportedFileError(ValueError):
    """Raised when no loader is registered for a file's extension."""


def register(*extensions: str) -> Callable[[Loader], Loader]:
    def wrap(fn: Loader) -> Loader:
        for ext in extensions:
            _LOADERS[ext.lower()] = fn
        return fn
    return wrap


def load_file(path: Path, display_name: str) -> list[Document]:
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        raise UnsupportedFileError(f"Unsupported file type: {path.suffix}")
    docs = loader(path)
    for doc in docs:
        doc.metadata["source"] = display_name
    return docs
```

## RAG Behaviour

- **Chunking:** `RecursiveCharacterTextSplitter` with `chunk_size=1000` and `chunk_overlap=150`, both configurable. CSV and Excel files produce one document per row (with a header-prefixed `col: value` format) and are not split further, unless a row is longer than the chunk size.
- **Metadata per chunk:** `source` (original filename), `page` for PDFs, `row` and `sheet` for CSV and Excel files, and `chunk_id`.
- **Duplicate handling:** a chunk's id is a hash of the source filename and its text. Uploading the same file twice to a collection does not create duplicate chunks.
- **Retrieval:** similarity search with `top_k=4` (configurable).
- **Grounding prompt:** the system prompt tells the model to answer only from the provided context, to cite sources as `[filename p.N]`, and to reply exactly `I couldn't find this in the uploaded documents.` when the context doesn't contain the answer.
- **No-context short-circuit:** if the collection is empty or retrieval returns nothing, the app returns the not-found message without calling the LLM.
- **Response object:** `Answer(text: str, sources: list[SourceRef])`. The UI renders the sources in an expander under each answer, showing the filename, page or row, and a snippet.

## UI (app.py)

- **Sidebar:**
  - A selector for the active document set, plus a "New document set" name field.
  - A file uploader that accepts multiple files of the supported types, and an "Index documents" button with a progress bar.
  - A list of the files in the active set, with chunk counts.
  - A "Delete document set" button that asks for confirmation.
- **Main area:** a chat interface (`st.chat_input` / `st.chat_message`) scoped to the active set. Each set has its own chat history in `st.session_state`.
- **Missing API key:** the chat input is disabled, and an `st.warning` explains how to set the key. Indexing still works without a key.

## Testing Strategy

- **Framework:** pytest. Tests live in `tests/`, with one test module per source module.
- **No network in tests.** Use LangChain's `DeterministicFakeEmbedding` and `FakeListChatModel` in place of the real embeddings and LLM. Chroma uses a pytest `tmp_path` directory.
- **Unit tests:** each loader against a tiny fixture file, chunking and metadata, slugifying collection names, duplicate-chunk ids, prompt assembly, and the no-context short-circuit.
- **Integration tests:** ingest fixtures, then retrieve, then run the chain with the fake LLM. Assert that the sources match the retrieved chunks. Also assert that two collections are isolated from each other.
- **UI smoke tests:** `streamlit.testing.v1.AppTest` checks that the app renders, that the chat is disabled without an API key, and that the collection selector lists existing sets.
- **Manual check:** a short smoke test with a real Groq key against two different document sets before release.
- **Coverage:** at least 80% line coverage on `rag_generator/`. `app.py` is covered by the smoke tests only.

## Boundaries

- **Always:**
  - Run `ruff check .` and `pytest -q` before every commit.
  - Read secrets only from env or `.env`.
  - Keep `streamlit` out of `rag_generator/`.
  - Cite sources in answers.
  - Update this spec when a decision changes.
- **Ask first:**
  - Adding a dependency that isn't listed above.
  - Changing the LLM provider default, the embedding model, or the Chroma persistence layout.
  - Adding OCR or multi-turn conversational retrieval.
  - Changing the not-found message contract.
- **Never:**
  - Commit `.env`, API keys or `data/`.
  - Call real APIs in tests.
  - Let the model answer from general knowledge when the context is empty.
  - Delete or skip failing tests to get to green.
  - Hard-code any document-specific logic.

## Success Criteria

1. `streamlit run app.py` starts with no code edits once `.env` holds a Groq key.
2. A user can upload at least one file of each type (PDF, TXT, MD, DOCX, HTML, CSV, XLSX), and each is indexed with a non-zero chunk count.
3. A question whose answer is in the documents gets a correct answer that cites at least one source with the right filename (and page or row).
4. A question unrelated to the documents returns `I couldn't find this in the uploaded documents.`
5. A user can create a second document set with different files and get answers from that set only, with no code changes and no restart.
6. Indexed sets are still listed and can be queried after the app restarts.
7. `pytest -q` passes offline, and coverage of `rag_generator/` is at least 80%.
8. `ruff check .` reports no errors.

## Open Questions

1. **Multi-turn follow-ups:** should a question like "what about the second one?" use chat history (a history-aware retriever)? The current plan says no for v1.
2. **Legacy `.xls`:** reading it needs the `xlrd` dependency. Is `.xlsx` enough?
3. **Groq rate limits:** is a friendly "rate limited, retry shortly" message enough, or do you want automatic retry with backoff?
