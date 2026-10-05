import pytest

from app.services.ingestion.chunker import PageText, chunk_pages


def test_chunks_keep_order_and_page_numbers() -> None:
    chunks = chunk_pages(
        [PageText(page_number=1, text="alpha"), PageText(page_number=2, text="beta")],
        chunk_size=800,
        overlap=100,
    )
    assert [chunk.content for chunk in chunks] == ["alpha", "beta"]
    assert [chunk.index for chunk in chunks] == [0, 1]
    assert [chunk.page_number for chunk in chunks] == [1, 2]


def test_overlap_repeats_the_previous_ending_without_dropping_text() -> None:
    text = "abcdefghijklmnopqrstuvwxyz"
    chunks = chunk_pages([PageText(page_number=None, text=text)], chunk_size=10, overlap=3)
    assert chunks[0].content == "abcdefghij"
    assert chunks[1].content.startswith("hij")
    rebuilt = chunks[0].content
    for chunk in chunks[1:]:
        rebuilt += chunk.content[3:]
    assert rebuilt == text
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_blank_pages_do_not_create_empty_chunks() -> None:
    chunks = chunk_pages(
        [PageText(page_number=1, text="   \n"), PageText(page_number=2, text="kept")],
        chunk_size=800,
        overlap=100,
    )
    assert len(chunks) == 1
    assert chunks[0].content == "kept"
    assert chunks[0].page_number == 2
    assert chunks[0].index == 0


def test_overlap_that_is_not_smaller_than_the_chunk_is_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_pages([PageText(page_number=1, text="hello")], chunk_size=10, overlap=10)
