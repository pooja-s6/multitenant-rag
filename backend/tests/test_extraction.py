from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.services.exceptions import BadRequest
from app.services.ingestion.text_extractor import extract_pages

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_documents"


def test_sample_pdf_keeps_page_numbers() -> None:
    pages = extract_pages(
        "employee_handbook.pdf",
        "application/pdf",
        (SAMPLES / "employee_handbook.pdf").read_bytes(),
    )
    assert [page.page_number for page in pages] == [1, 2]
    assert "09:00 to 17:30" in pages[0].text
    assert "20 days of annual leave" in pages[1].text


def test_engineering_guide_pdf_extracts_both_pages() -> None:
    pages = extract_pages(
        "engineering_guide.pdf",
        "application/pdf",
        (SAMPLES / "engineering_guide.pdf").read_bytes(),
    )
    assert [page.page_number for page in pages] == [1, 2]
    assert "code review" in pages[0].text
    assert "automated tests" in pages[1].text


def test_leave_policy_text_extracts_the_allowance() -> None:
    pages = extract_pages(
        "leave_policy.txt",
        "text/plain",
        (SAMPLES / "leave_policy.txt").read_bytes(),
    )
    assert pages[0].page_number is None
    assert "20 working days" in pages[0].text


def test_security_policy_markdown_keeps_the_words() -> None:
    pages = extract_pages(
        "security_policy.md",
        "text/markdown",
        (SAMPLES / "security_policy.md").read_bytes(),
    )
    assert "multi-factor authentication" in pages[0].text
    assert "12 characters" in pages[0].text
    assert "#" not in pages[0].text


def test_empty_and_unsupported_files_are_rejected() -> None:
    with pytest.raises(BadRequest):
        extract_pages("notes.docx", "application/octet-stream", b"hello")
    with pytest.raises(BadRequest):
        extract_pages("notes.txt", "text/plain", "not utf-8".encode("utf-16"))

    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    assert extract_pages("blank.pdf", "application/pdf", buffer.getvalue()) == []
