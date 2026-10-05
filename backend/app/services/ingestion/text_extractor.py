from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.services.exceptions import BadRequest
from app.services.ingestion.chunker import PageText
from app.services.ingestion.text_cleaner import clean_text, markdown_to_text

PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {".txt"}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
ALLOWED_EXTENSIONS = PDF_EXTENSIONS | TEXT_EXTENSIONS | MARKDOWN_EXTENSIONS

_EXTENSION_TYPES = {
    ".pdf": {"application/pdf", "application/x-pdf"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain"},
    ".markdown": {"text/markdown", "text/x-markdown", "text/plain"},
}
_GENERIC_TYPES = {"", "application/octet-stream"}


def extract_pages(filename: str, content_type: str | None, data: bytes) -> list[PageText]:
    extension = _extension(filename)
    _validate_content_type(extension, content_type)
    if extension in PDF_EXTENSIONS:
        return _pdf_pages(data)
    if extension in MARKDOWN_EXTENSIONS:
        text = markdown_to_text(_decode_utf8(data))
        return [PageText(page_number=None, text=text)] if text else []
    text = clean_text(_decode_utf8(data))
    return [PageText(page_number=None, text=text)] if text else []


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    if dot < 0:
        raise BadRequest("Unsupported file type. Upload a PDF, TXT, or Markdown file.")
    extension = filename[dot:].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise BadRequest("Unsupported file type. Upload a PDF, TXT, or Markdown file.")
    return extension


def _validate_content_type(extension: str, content_type: str | None) -> None:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type in _GENERIC_TYPES:
        return
    if media_type not in _EXTENSION_TYPES[extension]:
        raise BadRequest("File content type does not match its extension.")


def _decode_utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BadRequest("Text files must be UTF-8.") from exc


def _pdf_pages(data: bytes) -> list[PageText]:
    try:
        reader = PdfReader(BytesIO(data))
    except PdfReadError as exc:
        raise BadRequest("The PDF could not be read. Scanned documents need OCR, which is not enabled.") from exc
    if reader.is_encrypted:
        raise BadRequest("Encrypted PDFs are not supported.")

    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        cleaned = clean_text(extracted)
        if cleaned:
            pages.append(PageText(page_number=index, text=cleaned))
    return pages
