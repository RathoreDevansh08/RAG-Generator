# RAG-Generator

Agentic Coding Assessment

A general-purpose **Retrieval-Augmented Generation (RAG) generator**. Upload any set of documents at runtime and it builds a question-answering application over them. Answers are grounded in the content you provided.

## Problem Statement

Build a RAG Generator that:

- **Accepts documents at runtime.** Users upload their own files through the UI. Nothing is hard-coded or pre-indexed.
- **Creates a RAG application over those documents.** The uploaded content is processed, chunked, embedded and indexed so it can be retrieved.
- **Allows users to ask questions and receive grounded answers.** Answers come from the retrieved document content, not from the model's general knowledge.
- **Works with different document sets without code changes.** Switching to a new set of documents only needs a new upload. No configuration edits or redeployment.

## Tech Stack

The tech stack is fixed:

| Component | Technology |
|-----------|------------|
| Language  | Python     |
| UI        | Streamlit  |

## How It Works

1. **Upload:** The user uploads one or more documents in the Streamlit interface.
2. **Ingest:** The documents are parsed into text and split into chunks.
3. **Index:** Each chunk is embedded and stored in a vector index for that document set.
4. **Retrieve:** When a question is asked, the most relevant chunks are fetched from the index.
5. **Generate:** The question and the retrieved chunks are sent to the language model. It writes an answer based only on that context.
6. **Respond:** The answer is shown to the user. If the documents don't contain the answer, the app says so.

## Key Goals

- **Grounded:** Answers are based on the uploaded documents. The app avoids hallucinated content.
- **Generic:** One codebase works for any domain or document set.
- **Runtime-driven:** All document handling happens while the app is running, through the UI.
- **Simple to use:** A single Streamlit interface handles both uploading and asking questions.

## Features

- Supported formats: PDF, TXT, MD, DOCX, HTML, CSV, XLSX.
- Named document sets, persisted in ChromaDB, so you can switch between sets without re-uploading.
- Answers cite the source file and page (or row).
- If the documents don't contain the answer, the app returns a fixed not-found reply.

## Architecture

Built with LangChain. The LLM is Groq `openai/gpt-oss-20b`, called through the OpenAI-compatible API. Embeddings are computed locally with `all-MiniLM-L6-v2`. Vectors are stored in a persisted ChromaDB.

| Module | Role |
|--------|------|
| `app.py` | Streamlit UI |
| `rag_generator/config.py` | Settings loaded from env / `.env` |
| `rag_generator/loaders.py` | Per-format document loaders |
| `rag_generator/ingest.py` | Parsing and chunking |
| `rag_generator/store.py` | ChromaDB document-set storage and retrieval |
| `rag_generator/llm.py` | LLM client setup |
| `rag_generator/prompts.py` | Prompt templates |
| `rag_generator/chain.py` | Retrieve-and-answer chain |

See [SPEC.md](SPEC.md) and [tasks/plan.md](tasks/plan.md) for the full specification and plan.

## Setup & Run

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env            # then set LLM_API_KEY (free key from console.groq.com)

streamlit run app.py
```

The first run downloads the ~90MB embedding model.

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | (empty) | API key for the provider |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Model name |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model |
| `CHROMA_DIR` | `data/chroma` | ChromaDB persistence directory |
| `CHUNK_SIZE` | `1000` | Chunk size |
| `CHUNK_OVERLAP` | `150` | Chunk overlap |
| `TOP_K` | `4` | Chunks retrieved per question |

Switch providers by env only, with no code change:

- OpenRouter: `https://openrouter.ai/api/v1` / `openai/gpt-oss-20b:free`
- Ollama: `http://localhost:11434/v1` / `gpt-oss:20b`
- OpenAI: `https://api.openai.com/v1` / `gpt-4o-mini`

## Testing

```bash
pytest -q
ruff check .
```

Tests run offline using fake embeddings and a fake LLM.

## Limitations

- No OCR, so scanned PDFs are not supported.
- Single-turn questions only (no conversation memory).
- Groq free-tier rate limits apply.
- Local, single-user app.
