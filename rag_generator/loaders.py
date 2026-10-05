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


@register(".pdf")
def _load_pdf(path: Path) -> list[Document]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return [
        Document(page_content=page.extract_text() or "", metadata={"page": i})
        for i, page in enumerate(reader.pages, start=1)
    ]


@register(".docx")
def _load_docx(path: Path) -> list[Document]:
    import docx2txt

    return [Document(page_content=docx2txt.process(str(path)) or "")]


@register(".html", ".htm")
def _load_html(path: Path) -> list[Document]:
    from bs4 import BeautifulSoup

    html = path.read_text(encoding="utf-8", errors="replace")
    text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
    return [Document(page_content=text)]


def _rows_to_docs(df, extra: dict | None = None) -> list[Document]:
    import pandas as pd

    docs = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        text = "\n".join(f"{col}: {val}" for col, val in row.items() if not pd.isna(val))
        meta = {"row": i, "tabular": True, **(extra or {})}
        docs.append(Document(page_content=text, metadata=meta))
    return docs


@register(".csv")
def _load_csv(path: Path) -> list[Document]:
    import pandas as pd

    return _rows_to_docs(pd.read_csv(path))


@register(".xlsx")
def _load_xlsx(path: Path) -> list[Document]:
    import pandas as pd

    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    docs: list[Document] = []
    for name, df in sheets.items():
        docs.extend(_rows_to_docs(df, {"sheet": str(name)}))
    return docs


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
