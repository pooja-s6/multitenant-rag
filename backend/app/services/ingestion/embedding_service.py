import hashlib
from typing import Protocol

from app.config import get_settings
from app.services.exceptions import IngestionError
from app.vector_dimensions import DEFAULT_EMBEDDING_MODEL, EMBEDDING_VECTOR_DIMENSION


class EmbeddingService(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the same order."""


class SentenceTransformerEmbeddingService:
    """Loads the configured model once and embeds chunks in a batch."""

    def __init__(self, model_name: str, dimension: int) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._model: object | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        encoded = model.encode(  # type: ignore[attr-defined]
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors = [[float(value) for value in row] for row in encoded]
        _require_dimension(vectors, self.dimension)
        return vectors

    def _load(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise IngestionError(
                "sentence-transformers is not installed. Install the ML requirements to embed documents."
            ) from exc
        model = SentenceTransformer(self.model_name)
        actual = int(model.get_sentence_embedding_dimension())
        if actual != self.dimension:
            raise IngestionError(
                f"Model {self.model_name} returns {actual} dimensions, "
                f"but EMBEDDING_DIMENSION is {self.dimension}."
            )
        self._model = model
        return model


class DeterministicEmbeddingService:
    """Stable vectors for tests. The width matches the pgvector column."""

    def __init__(self, dimension: int = EMBEDDING_VECTOR_DIMENSION) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values: list[float] = []
            while len(values) < self.dimension:
                digest = hashlib.sha256(digest).digest()
                values.extend(byte / 255.0 for byte in digest)
            vectors.append(values[: self.dimension])
        return vectors


def _require_dimension(vectors: list[list[float]], dimension: int) -> None:
    for vector in vectors:
        if len(vector) != dimension:
            raise IngestionError(
                f"Model returned {len(vector)} dimensions, but EMBEDDING_DIMENSION is {dimension}."
            )


_cached: SentenceTransformerEmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _cached
    settings = get_settings()
    if settings.embedding_model == DEFAULT_EMBEDDING_MODEL and (
        settings.embedding_dimension != EMBEDDING_VECTOR_DIMENSION
    ):
        raise IngestionError(
            f"{DEFAULT_EMBEDDING_MODEL} uses {EMBEDDING_VECTOR_DIMENSION} dimensions. "
            "EMBEDDING_DIMENSION must match the database column."
        )
    if (
        _cached is None
        or _cached.model_name != settings.embedding_model
        or _cached.dimension != settings.embedding_dimension
    ):
        _cached = SentenceTransformerEmbeddingService(settings.embedding_model, settings.embedding_dimension)
    return _cached
