import tempfile
from pathlib import Path

import streamlit as st

from rag_generator import store as store_mod
from rag_generator.chain import answer_question
from rag_generator.config import get_settings
from rag_generator.ingest import ingest_files
from rag_generator.llm import build_llm
from rag_generator.loaders import (
    SUPPORTED_EXTENSIONS,
    EmptyDocumentError,
    UnsupportedFileError,
)

st.set_page_config(page_title="RAG Generator", page_icon="📚")
settings = get_settings()


@st.cache_resource
def get_store(chroma_dir: str, embedding_model: str):
    return store_mod.DocumentStore(chroma_dir, store_mod.get_embeddings(settings))


store = get_store(str(settings.chroma_dir), str(settings.embedding_model))
history_all = st.session_state.setdefault("history", {})

with st.sidebar:
    st.header("Document sets")
    collections = store.list_collections()
    active = st.session_state.get("active")
    if active and active not in collections:
        collections = [active] + collections
    if collections:
        idx = collections.index(active) if active in collections else 0
        active = st.selectbox("Active set", collections, index=idx)
        st.session_state["active"] = active
    else:
        active = None

    new_name = st.text_input("New document set name")
    if st.button("Create"):
        try:
            st.session_state["active"] = store_mod.slugify(new_name)
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    files = st.file_uploader(
        "Upload documents",
        accept_multiple_files=True,
        type=[e.lstrip(".") for e in SUPPORTED_EXTENSIONS],
    )
    if st.button("Index documents", disabled=not (active and files)):
        with tempfile.TemporaryDirectory() as tmp:
            for f in files:
                path = Path(tmp) / f.name
                path.write_bytes(f.getbuffer())
                try:
                    with st.spinner(f"Indexing {f.name}..."):
                        res = ingest_files(store, active, [(path, f.name)], settings)
                    st.success(f"{f.name}: {sum(res.values())} chunks")
                except (UnsupportedFileError, EmptyDocumentError) as e:
                    st.error(f"{f.name}: {e}")

    if active:
        st.divider()
        sources_in_set = store.list_sources(active)
        if not sources_in_set:
            st.caption("No documents indexed yet.")
        for src, n in sources_in_set.items():
            st.caption(f"{src} — {n} chunks")
        confirm = st.checkbox("Confirm delete")
        if st.button("Delete document set", disabled=not confirm):
            store.delete_collection(active)
            history_all.pop(active, None)
            st.session_state.pop("active", None)
            st.rerun()

st.title("📚 RAG Generator")
st.caption("Ask questions about your own documents.")


def render_sources(sources):
    with st.expander("Sources"):
        for s in sources:
            loc = f" p.{s.page}" if s.page else (f" row {s.row}" if s.row else "")
            st.markdown(f"**{s.source}**{loc}")
            st.caption(s.snippet)


if not active:
    st.info("Create a document set and upload files in the sidebar to begin.")
else:
    history = history_all.setdefault(active, [])
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                render_sources(msg["sources"])

    if not settings.llm_api_key:
        st.warning(
            "Set LLM_API_KEY in .env (free key: https://console.groq.com/keys) to enable chat."
        )
        st.chat_input("Ask a question", disabled=True)
    else:
        prompt = st.chat_input("Ask a question about your documents")
        if prompt:
            with st.chat_message("user"):
                st.markdown(prompt)
            try:
                with st.spinner("Thinking..."):
                    ans = answer_question(
                        prompt,
                        store.get_retriever(active, settings.top_k),
                        build_llm(settings),
                    )
                history.append({"role": "user", "content": prompt})
                history.append({"role": "assistant", "content": ans.text, "sources": ans.sources})
                with st.chat_message("assistant"):
                    st.markdown(ans.text)
                    if ans.sources:
                        render_sources(ans.sources)
            except Exception as e:
                st.error(
                    "Rate limited by the LLM provider — wait a few seconds and retry."
                    if "rate" in str(e).lower()
                    else f"LLM error: {e}"
                )
