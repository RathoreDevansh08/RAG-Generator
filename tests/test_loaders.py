from pathlib import Path

import pytest

from rag_generator.loaders import (
    SUPPORTED_EXTENSIONS,
    EmptyDocumentError,
    UnsupportedFileError,
    load_file,
)


def test_txt_loads_with_source_metadata(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    docs = load_file(f, "original.txt")
    assert len(docs) == 1
    assert docs[0].page_content == "hello world"
    assert docs[0].metadata["source"] == "original.txt"


def test_uppercase_md_extension(tmp_path: Path) -> None:
    f = tmp_path / "README.MD"
    f.write_text("# Title\nbody", encoding="utf-8")
    assert load_file(f, "README.MD")[0].metadata["source"] == "README.MD"


@pytest.mark.parametrize("content", ["", "   \n\t\n"])
def test_empty_file_raises(tmp_path: Path, content: str) -> None:
    f = tmp_path / "e.txt"
    f.write_text(content, encoding="utf-8")
    with pytest.raises(EmptyDocumentError, match="No text could be extracted from e.txt"):
        load_file(f, "e.txt")


def test_unknown_extension_raises(tmp_path: Path) -> None:
    f = tmp_path / "a.xyz"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(UnsupportedFileError):
        load_file(f, "a.xyz")


def test_supported_extensions() -> None:
    assert ".txt" in SUPPORTED_EXTENSIONS
    assert ".md" in SUPPORTED_EXTENSIONS
