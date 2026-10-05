import re

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MARKDOWN_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_HEADING = re.compile(r"^#{1,6}\s*", re.MULTILINE)


def clean_text(text: str) -> str:
    """Collapse noisy whitespace without changing the words."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _CONTROL_CHARACTERS.sub("", normalized)
    normalized = normalized.replace("\t", " ")
    normalized = re.sub(r"[ ]{2,}", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    lines = [line.strip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def markdown_to_text(text: str) -> str:
    """Keep the readable words from light Markdown."""
    without_fences = _MARKDOWN_FENCE.sub(" ", text)
    without_code = _INLINE_CODE.sub(r"\1", without_fences)
    without_images = _IMAGE.sub(r"\1", without_code)
    without_links = _LINK.sub(r"\1", without_images)
    without_headings = _HEADING.sub("", without_links)
    plain = without_headings.replace("**", "").replace("__", "")
    return clean_text(plain)
