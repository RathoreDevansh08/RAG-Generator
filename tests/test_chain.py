from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel
from langchain_core.retrievers import BaseRetriever

from rag_generator.chain import (
    NOT_FOUND_MESSAGE,
    answer_question,
    citation_label,
)


class StubRetriever(BaseRetriever):
    docs: list[Document]

    def _get_relevant_documents(self, query, *, run_manager=None):
        return self.docs


class ExplodingLLM(FakeListChatModel):
    def _generate(self, *args, **kwargs):
        raise AssertionError("LLM must not be called")


def _doc():
    return Document(page_content="Revenue was 10M.", metadata={"source": "report.pdf", "page": 2})


def test_sources_returned_with_page():
    llm = FakeListChatModel(responses=["Revenue was 10M [report.pdf p.2]"])
    ans = answer_question("revenue?", StubRetriever(docs=[_doc()]), llm)
    assert "10M" in ans.text
    assert len(ans.sources) == 1
    assert ans.sources[0].source == "report.pdf"
    assert ans.sources[0].page == 2
    assert ans.sources[0].row is None


def test_no_docs_short_circuits():
    ans = answer_question("x?", StubRetriever(docs=[]), ExplodingLLM(responses=["a"]))
    assert ans.text == NOT_FOUND_MESSAGE
    assert ans.sources == []


def test_not_found_reply_clears_sources():
    llm = FakeListChatModel(responses=[NOT_FOUND_MESSAGE])
    ans = answer_question("x?", StubRetriever(docs=[_doc()]), llm)
    assert ans.text == NOT_FOUND_MESSAGE
    assert ans.sources == []


def test_citation_label_variants():
    assert (
        citation_label(Document(page_content="", metadata={"source": "a.pdf", "page": 3}))
        == "[a.pdf p.3]"
    )
    assert (
        citation_label(Document(page_content="", metadata={"source": "a.csv", "row": 5}))
        == "[a.csv row 5]"
    )
    assert citation_label(Document(page_content="", metadata={"source": "a.txt"})) == "[a.txt]"
