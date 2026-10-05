from langchain_core.prompts import ChatPromptTemplate

NOT_FOUND_MESSAGE = "I couldn't find this in the uploaded documents."

_SYSTEM = f"""You are a question-answering assistant for uploaded documents.
Rules:
- Answer ONLY using the provided context. Do not use outside knowledge.
- Cite sources inline using the bracketed labels shown in the context, e.g. [report.pdf p.2] or [data.csv row 5].
- If the context does not contain the answer, reply exactly with: {NOT_FOUND_MESSAGE} and nothing else.
- Be concise."""

QA_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)
