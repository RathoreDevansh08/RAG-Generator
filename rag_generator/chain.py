from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever

from rag_generator.prompts import NOT_FOUND_MESSAGE, QA_PROMPT

__all__ = [
    "NOT_FOUND_MESSAGE",
    "SourceRef",
    "Answer",
    "citation_label",
    "format_context",
    "answer_question",
]


@dataclass
class SourceRef:
    source: str
    page: int | None
    row: int | None
    snippet: str


@dataclass
class Answer:
    text: str
    sources: list[SourceRef]


def citation_label(doc) -> str:
    meta = doc.metadata
    src = meta.get("source", "unknown")
    if meta.get("page") is not None:
        return f"[{src} p.{meta['page']}]"
    if meta.get("row") is not None:
        return f"[{src} row {meta['row']}]"
    return f"[{src}]"


def format_context(docs) -> str:
    return "\n\n".join(f"{citation_label(d)}\n{d.page_content}" for d in docs)


def answer_question(question: str, retriever: BaseRetriever, llm: BaseChatModel) -> Answer:
    docs = retriever.invoke(question)
    if not docs:
        return Answer(NOT_FOUND_MESSAGE, [])
    text = (
        (QA_PROMPT | llm | StrOutputParser())
        .invoke({"context": format_context(docs), "question": question})
        .strip()
    )
    if NOT_FOUND_MESSAGE in text:
        return Answer(NOT_FOUND_MESSAGE, [])
    sources = [
        SourceRef(
            source=d.metadata.get("source", "unknown"),
            page=d.metadata.get("page"),
            row=d.metadata.get("row"),
            snippet=d.page_content[:200],
        )
        for d in docs
    ]
    return Answer(text, sources)
