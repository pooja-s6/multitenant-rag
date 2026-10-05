from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    page_number: int | None
    text: str


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    page_number: int | None


def chunk_pages(pages: list[PageText], chunk_size: int, overlap: int) -> list[TextChunk]:
    """Split page text in order. Overlap must be smaller than the chunk size."""
    if chunk_size <= 0:
        raise ValueError("CHUNK_SIZE must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")

    chunks: list[TextChunk] = []
    for page in pages:
        for piece in _split(page.text, chunk_size, overlap):
            chunks.append(TextChunk(index=len(chunks), content=piece, page_number=page.page_number))
    return chunks


def _split(text: str, chunk_size: int, overlap: int) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    pieces: list[str] = []
    start = 0
    length = len(stripped)
    while start < length:
        end = min(start + chunk_size, length)
        piece = stripped[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= length:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = start + 1
        start = next_start
    return pieces
