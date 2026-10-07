import re

from app.services.exceptions import BadRequest

_MAX_QUERY_CHARS = 4000
_WHITESPACE = re.compile(r"\s+")


def preprocess_query(query: str) -> str:
    """Trim a question without changing its words."""
    cleaned = _WHITESPACE.sub(" ", query.replace("\x00", "")).strip()
    if not cleaned:
        raise BadRequest("Query text is required.")
    if len(cleaned) > _MAX_QUERY_CHARS:
        raise BadRequest(f"Query must be {_MAX_QUERY_CHARS} characters or fewer.")
    return cleaned
