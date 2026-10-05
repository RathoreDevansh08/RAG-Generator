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
