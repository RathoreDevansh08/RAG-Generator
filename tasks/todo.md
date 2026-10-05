# RAG-Generator: Task List

See [plan.md](plan.md) for the architecture, interface contracts and risks. All commands below are run with `.venv` activated.

---

## Phase 1: Foundation and a thin end-to-end slice

## Task 1: Tooling and test scaffolding ✅ verified (69 tests pass, ruff clean)

**Description:** Add the project config and the shared offline test fixtures, so every later task can be tested without network access.

**Acceptance criteria:**
- [x] `pyproject.toml` sets ruff (line length 100, py311) and pytest (`testpaths = ["tests"]`)
- [x] `.env.example` lists `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL`, `CHROMA_DIR`, `CHUNK_SIZE`, `CHUNK_OVERLAP` and `TOP_K`
- [x] `tests/conftest.py` provides the `settings` (a tmp Chroma dir), `fake_embeddings` (`DeterministicFakeEmbedding(size=64)`) and `store` fixtures

**Verification:**
- [x] `pytest -q` runs with no errors (0 tests collected is fine)
- [x] `ruff check .` is clean

**Dependencies:** None

**Files:** `pyproject.toml`, `.env.example`, `.streamlit/config.toml`, `tests/conftest.py`

**Scope:** XS

---

## Task 2: Index TXT/MD files into a named document set ✅ verified (69 tests pass, ruff clean)

**Description:** Build the ingest path for plain text: load the file, split it into chunks with deterministic ids, and upsert them into a slugified Chroma collection.

**Acceptance criteria:**
- [x] `load_file` handles `.txt` and `.md`, sets `source`, and raises `UnsupportedFileError` or `EmptyDocumentError` when appropriate
- [x] `ingest_files` returns the chunk count per file. Ingesting the same file twice leaves `count()` unchanged.
- [x] Two collections are isolated from each other, and `slugify("My Docs!")` returns `"my-docs"`

**Verification:**
- [x] `pytest tests/test_loaders.py tests/test_ingest.py tests/test_store.py -q`

**Dependencies:** Task 1

**Files:** `rag_generator/loaders.py`, `rag_generator/ingest.py`, `rag_generator/store.py`, `tests/test_loaders.py`, `tests/test_ingest.py`, `tests/test_store.py`

**Scope:** M

---

## Task 3: Answer a question with citations and the not-found fallback ✅ verified (69 tests pass, ruff clean)

**Description:** Build the grounded QA chain: retrieve chunks, fill in a strict prompt, call the LLM, and return the answer text with source references.

**Acceptance criteria:**
- [x] `answer_question` returns an `Answer` whose `sources` match the retrieved chunks (source, page or row, snippet)
- [x] When retrieval returns nothing, it returns `NOT_FOUND_MESSAGE` without calling the LLM
- [x] When the LLM replies with the not-found message, `sources` is empty

**Verification:**
- [x] `pytest tests/test_chain.py -q`, using `FakeListChatModel` and a stub retriever

**Dependencies:** Task 1 (it can run in parallel with Task 2)

**Files:** `rag_generator/prompts.py`, `rag_generator/llm.py`, `rag_generator/chain.py`, `tests/test_chain.py`

**Scope:** M

---

## Task 4: Minimal Streamlit UI ✅ verified (69 tests pass, ruff clean)

**Description:** Wire up `app.py`. The user creates or picks a document set, uploads files, clicks Index, then chats. Each answer shows a Sources expander.

**Acceptance criteria:**
- [x] A new set can be created from the sidebar, and an uploaded `.txt` file is indexed with a success message showing its chunk count
- [x] Chat answers render with a Sources expander
- [x] The app calls `store.get_embeddings` through module attribute access, cached with `@st.cache_resource`

**Verification:**
- [x] `pytest tests/test_app.py -q` (an `AppTest` smoke test that renders the app without exceptions)
- [ ] Manual check: run `streamlit run app.py` with a real Groq key, then upload a txt file and ask a question

**Dependencies:** Task 2, Task 3

**Files:** `app.py`, `tests/test_app.py`

**Scope:** M

---

## Checkpoint A: End-to-end on text files
- [x] `pytest -q` and `ruff check .` pass
- [ ] Manual check: a question answered from the docs shows a citation, and an unrelated question returns the exact not-found message
- [ ] **This is the minimum deliverable that meets the core assessment requirements**

---

## Phase 2: Formats

## Task 5: PDF, DOCX and HTML loaders ✅ verified (69 tests pass, ruff clean)

**Description:** Register loaders for PDF (one document per page, with a 1-based `page`), DOCX (`docx2txt`) and HTML (BeautifulSoup text).

**Acceptance criteria:**
- [x] Each PDF page becomes its own document with `metadata["page"]`, and the answer cites it as `[file p.N]`
- [x] DOCX and HTML files produce non-empty text, with markup removed from HTML
- [x] A PDF with no extractable text raises `EmptyDocumentError`

**Verification:**
- [x] `pytest tests/test_loaders.py -q`, with fixtures generated at test time using fpdf2 and python-docx

**Dependencies:** Task 2

**Files:** `rag_generator/loaders.py`, `tests/test_loaders.py`

**Scope:** S

---

## Task 6: CSV and XLSX loaders ✅ verified (69 tests pass, ruff clean)

**Description:** Turn each row into one document (`col: value` lines) with `row`, `sheet` and `tabular=True`. Chunking leaves tabular documents unsplit.

**Acceptance criteria:**
- [x] A CSV with N rows gives N documents with `row` from 1 to N
- [x] Every sheet in an XLSX file is loaded with `metadata["sheet"]`
- [x] `split_documents` doesn't split short tabular rows

**Verification:**
- [x] `pytest tests/test_loaders.py tests/test_ingest.py -q`

**Dependencies:** Task 2 (if run in parallel with Task 5, the same agent must own `loaders.py`)

**Files:** `rag_generator/loaders.py`, `tests/test_loaders.py`, `tests/test_ingest.py`

**Scope:** S

---

## Checkpoint B: All formats
- [ ] A fixture of every supported type (PDF, TXT, MD, DOCX, HTML, CSV, XLSX) indexes with a chunk count above 0
- [x] `pytest -q` passes

---

## Phase 3: Set management and polish

## Task 7: Document set management

**Description:** Let users switch between saved sets, see each set's files with chunk counts, delete a set after confirming, and keep a separate chat history per set.

**Acceptance criteria:**
- [x] After a restart, the sets created earlier are listed and can be queried
- [x] Switching sets shows that set's chat history and sources only
- [x] Delete removes the collection, but only after the confirmation checkbox is ticked

**Verification:**
- [x] `pytest tests/test_store.py tests/test_app.py -q`
- [ ] Manual check: create two sets with different docs, then confirm that answers come only from the active set

**Dependencies:** Task 4

**Files:** `app.py`, `rag_generator/store.py`, `tests/test_app.py`

**Scope:** S

---

## Task 8: Error handling and UX

**Description:** Make the app fail gracefully.

**Acceptance criteria:**
- [x] If `LLM_API_KEY` is missing, a warning explains how to get a free Groq key and chat input is disabled, while indexing still works
- [ ] An unsupported or empty file shows a per-file `st.error`, and the other files still get indexed
- [x] LLM errors show a friendly message, with a specific hint when the error is a rate limit

**Verification:**
- [x] `pytest tests/test_app.py -q`, which checks the warning and the disabled chat when no key is set

**Dependencies:** Task 4 (run it after Task 7, since both edit `app.py`)

**Files:** `app.py`, `tests/test_app.py`

**Scope:** S

---

## Task 9: Docs, config and the quality gate

**Description:** Finish the README (features, architecture, setup and run, configuration, testing, limitations) and meet the coverage and lint bar.

**Acceptance criteria:**
- [ ] A new reader can follow the README to set up and run the app
- [x] Coverage of `rag_generator/` is at least 80%
- [x] `ruff check .` and `ruff format --check .` are clean

**Verification:**
- [x] `pytest --cov=rag_generator --cov-report=term-missing`
- [x] `ruff check . && ruff format --check .`

**Dependencies:** Tasks 1–8

**Files:** `README.md`, `.gitignore`, any test files needed to reach the coverage target

**Scope:** S

---

## Checkpoint C: Complete
- [ ] All SPEC Success Criteria (1–8) are met
- [ ] Human review before committing
