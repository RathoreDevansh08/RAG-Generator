"""Load uploaded files into LangChain Documents, one loader per extension."""

from collections.abc import Callable
from pathlib import Path

from langchain_core.documents import Document

Loader = Callable[[Path], list[Document]]
_LOADERS: dict[str, Loader] = {}


class UnsupportedFileError(ValueError):
    """Raised when no loader is registered for a file's extension."""


class EmptyDocumentError(ValueError):
    """Raised when a file yields no extractable text."""


def register(*extensions: str) -> Callable[[Loader], Loader]:
    def wrap(fn: Loader) -> Loader:
        for ext in extensions:
            _LOADERS[ext.lower()] = fn
        return fn

    return wrap


@register(".txt", ".md")
def _load_text(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [Document(page_content=text)]


def load_file(path: Path, display_name: str) -> list[Document]:
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        raise UnsupportedFileError(f"Unsupported file type: {path.suffix}")
    docs = [d for d in loader(path) if d.page_content.strip()]
    if not docs:
        raise EmptyDocumentError(f"No text could be extracted from {display_name}")
    for doc in docs:
        doc.metadata["source"] = display_name
    return docs


SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(sorted(_LOADERS))
