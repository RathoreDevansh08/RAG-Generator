# Implementation Plan: RAG-Generator

## Overview

This plan builds the Streamlit + LangChain RAG app defined in [SPEC.md](../SPEC.md). Users upload documents at runtime into named document sets, which are saved in a persistent ChromaDB store. They then ask questions and get answers from Groq `openai/gpt-oss-20b`, grounded in the documents and citing their sources. The work is cut into vertical slices: the first slice delivers a working end-to-end path for plain-text files, and later slices add formats, set management and polish on top of it.

**Already in place:**
- `SPEC.md` and `README.md`
- `requirements.txt` and `requirements-dev.txt`
- `rag_generator/config.py`
- A `.venv` install running in the background

## Architecture Decisions

- **Logic and UI are separate.** All logic lives in `rag_generator/`, which never imports Streamlit, and `app.py` only orchestrates. This keeps the whole pipeline testable without the UI.
- **Dependencies are passed in.** Embeddings, the LLM and the Chroma path are passed as arguments, so tests run offline with `DeterministicFakeEmbedding` and `FakeListChatModel`.
- **Each document set is one Chroma collection.** Collection names are slugified, so new sets need no code change and survive restarts.
- **Chunk ids are deterministic:** `sha256(source + "\0" + text)[:32]`. Re-uploading the same file overwrites its chunks instead of duplicating them.
- **Not-found is a fixed contract.** The app returns the exact `NOT_FOUND_MESSAGE`. When retrieval finds nothing, it returns that message without calling the LLM.
- **Loaders use a registry** (`@register(".ext")`). A new format is one function and doesn't change the rest of the pipeline.
- **The LLM is set by env vars.** It's built with `ChatOpenAI(base_url, api_key, model)`, so moving from Groq to OpenRouter, Ollama or OpenAI is a `.env` change.

## Dependency Graph

```
config.py (done)
   │
   ├── loaders.py ──┐
   │                ├── ingest.py ──┐
   ├── store.py ────┘               │
   │      │                         │
   ├── prompts.py ── chain.py ──────┼── app.py
   └── llm.py ──────────┘           │
                                    │
tests/conftest.py (fakes) ─── all tests
```

## Interface Contracts (fixed before any parallel work)

```python
# loaders.py
SUPPORTED_EXTENSIONS: tuple[str, ...]
class UnsupportedFileError(ValueError): ...
class EmptyDocumentError(ValueError): ...
def load_file(path: Path, display_name: str) -> list[Document]
# metadata: source; page (pdf, 1-based); row, sheet, tabular=True (csv/xlsx)

# store.py
def slugify(name: str) -> str
def get_embeddings(settings: Settings) -> Embeddings
class DocumentStore:
    def __init__(self, persist_dir: str, embeddings: Embeddings)
    def list_collections(self) -> list[str]
    def add_documents(self, collection: str, docs: list[Document]) -> int
    def count(self, collection: str) -> int
    def list_sources(self, collection: str) -> dict[str, int]
    def delete_collection(self, collection: str) -> None
    def get_retriever(self, collection: str, k: int) -> BaseRetriever

# ingest.py
def split_documents(docs: list[Document], settings: Settings) -> list[Document]
def ingest_files(store, collection: str, files: list[tuple[Path, str]],
                 settings: Settings) -> dict[str, int]

# llm.py
def build_llm(settings: Settings) -> BaseChatModel

# prompts.py
NOT_FOUND_MESSAGE = "I couldn't find this in the uploaded documents."
QA_PROMPT: ChatPromptTemplate  # vars: context, question

# chain.py
@dataclass class SourceRef: source: str; page: int | None; row: int | None; snippet: str
@dataclass class Answer: text: str; sources: list[SourceRef]
def answer_question(question: str, retriever: BaseRetriever, llm: BaseChatModel) -> Answer
```

## Task List

### Phase 1: Foundation and a thin end-to-end slice
- [ ] **Task 1:** Tooling and test scaffolding (XS)
- [ ] **Task 2:** Index TXT/MD files into a named document set (M)
- [ ] **Task 3:** Answer a question with citations and the not-found fallback (M)
- [ ] **Task 4:** Minimal Streamlit UI: create a set, upload, index, chat (M)

### Checkpoint A: End-to-end on text files
- [ ] `pytest -q` and `ruff check .` pass
- [ ] Manual check: upload a `.txt` file, ask a question, see a cited answer. An unrelated question returns the not-found message.

### Phase 2: Formats
- [ ] **Task 5:** PDF, DOCX and HTML loaders, with page citations for PDFs (S)
- [ ] **Task 6:** CSV and XLSX loaders, with row and sheet citations (S)

### Checkpoint B: All formats
- [ ] Every supported format indexes with a non-zero chunk count, and tests pass

### Phase 3: Set management and polish
- [ ] **Task 7:** Switch, list, delete and persist document sets, with per-set chat history (S)
- [ ] **Task 8:** Error handling and UX: missing key, bad or empty files, rate limits (S)
- [ ] **Task 9:** Docs, config files and the quality gate (S)

### Checkpoint C: Complete
- [ ] All SPEC Success Criteria (1–8) are met
- [ ] Coverage of `rag_generator/` is at least 80%, and `ruff check .` is clean
- [ ] Human review

## Parallelization

The contracts are fixed above, so tasks can run in parallel once their prerequisites are done:

| Wave | Tasks in parallel | Needs |
|---|---|---|
| 1 | Task 1 | — |
| 2 | Task 2 and Task 3 | Task 1 |
| 3 | Task 4, Task 5 and Task 6 | Task 2 (Task 4 also needs Task 3) |
| 4 | Task 7, Task 8 and Task 9 | Task 4 |

**File ownership per wave** (no two agents edit the same file):
- Task 5 and Task 6 both add functions to `loaders.py`. Either one agent owns both tasks, or they run one after the other.
- Task 7 and Task 8 both touch `app.py`. Run them one after the other, or give one agent both.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The torch / sentence-transformers install is slow (hundreds of MB) | High | Install in the background now, using the CPU wheel. Tests never load the real model. |
| The first run downloads the embedding model (about 90 MB) | Med | Cache it with `@st.cache_resource` and say so in the README. |
| Groq free-tier rate limits | Med | Catch the error and show a friendly retry message. |
| `gpt-oss` ignores the exact not-found wording | Med | Use a strict prompt with temperature 0. Detect the message by checking whether the reply contains it. Also short-circuit when retrieval finds nothing. |
| Chroma metadata rejects `None` and non-scalar values | Low | Drop `None` values in `split_documents`. |
| Streamlit's `AppTest` doesn't pick up the monkeypatched embeddings | Low | Have `app.py` call `store.get_embeddings` through attribute access on the module. |
| The 18-minute time box | High | Phase 1 alone meets the core assessment goals. Phase 2 and 3 tasks can be cut in reverse order (9, 8, 7, then 6). |

## Open Questions

- If time runs out, are Phase 1 plus Task 5 (PDF) an acceptable minimum to deliver?
