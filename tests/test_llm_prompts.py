from rag_generator.chain import NOT_FOUND_MESSAGE as CHAIN_NOT_FOUND
from rag_generator.config import Settings
from rag_generator.llm import build_llm
from rag_generator.prompts import NOT_FOUND_MESSAGE, QA_PROMPT


def test_not_found_message_contract():
    assert NOT_FOUND_MESSAGE == "I couldn't find this in the uploaded documents."
    assert CHAIN_NOT_FOUND == NOT_FOUND_MESSAGE


def test_prompt_variables():
    assert set(QA_PROMPT.input_variables) == {"context", "question"}


def test_prompt_enforces_grounding_and_citations():
    messages = QA_PROMPT.format_messages(context="[a.txt]\nAlpha", question="What?")
    system, human = messages[0].content, messages[-1].content
    assert NOT_FOUND_MESSAGE in system
    assert "ONLY" in system
    assert "cite" in system.lower()
    assert "[a.txt]\nAlpha" in human
    assert "What?" in human


def test_prompt_handles_braces_in_context():
    messages = QA_PROMPT.format_messages(context='{"json": 1}', question="q")
    assert '{"json": 1}' in messages[-1].content


def test_build_llm_uses_settings_without_network():
    s = Settings(llm_base_url="https://example.test/v1", llm_api_key="sk-x", llm_model="m-1")
    llm = build_llm(s)
    assert llm.model_name == "m-1"
    assert llm.temperature == 0
    assert str(llm.openai_api_base) == "https://example.test/v1"
    assert llm.openai_api_key.get_secret_value() == "sk-x"
