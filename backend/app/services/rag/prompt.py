from app.services.retrieval.search import RetrievedChunk

_SYSTEM = (
    "Answer only from the numbered excerpts. "
    "If they do not contain the answer, say you cannot find it in the documents. "
    "Mention the source filename when you use an excerpt."
)


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> tuple[str, str]:
    """Return the system message and the user message for the provider."""
    if not chunks:
        excerpts = "No excerpts were retrieved."
    else:
        lines = []
        for number, chunk in enumerate(chunks, start=1):
            page = "unknown" if chunk.page_number is None else str(chunk.page_number)
            lines.append(f"[{number}] {chunk.filename} page {page}\n{chunk.content}")
        excerpts = "\n\n".join(lines)
    user = f"Excerpts:\n{excerpts}\n\nQuestion: {question}"
    return _SYSTEM, user
