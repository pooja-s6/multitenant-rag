import re
from dataclasses import dataclass

from app.config import Settings
from app.services.retrieval.search import RetrievedChunk

_COMPLEX_PHRASES = (
    "compare",
    "comparison",
    "versus",
    " vs ",
    "difference",
    "why ",
    "why?",
    "explain",
    "tradeoff",
    "trade-off",
)


@dataclass(frozen=True)
class RouteDecision:
    model: str
    score: float
    input_price: float
    output_price: float


def decide(query: str, *, chunks: list[RetrievedChunk], settings: Settings) -> RouteDecision:
    """Pick the small or large model from a score in the unit interval.

    A score at or below ROUTING_COMPLEXITY_THRESHOLD uses SMALL_MODEL.
    A higher score uses LARGE_MODEL. Prices come from settings for that model.
    """
    top_score = chunks[0].score if chunks else None
    score = complexity_score(query, chunk_count=len(chunks), top_score=top_score)
    if score > settings.routing_complexity_threshold:
        return RouteDecision(
            model=settings.large_model,
            score=score,
            input_price=settings.large_model_price,
            output_price=settings.large_model_output_price,
        )
    return RouteDecision(
        model=settings.small_model,
        score=score,
        input_price=settings.small_model_price,
        output_price=settings.small_model_output_price,
    )


def complexity_score(query: str, *, chunk_count: int, top_score: float | None) -> float:
    """Weighted score from length, sentences, question type, retrieval, and ambiguity.

    Weights: length 0.25, sentences 0.15, question type 0.25, low retrieval
    confidence 0.15, chunk count 0.10, ambiguity 0.10. Each part is in 0..1.
    """
    words = [word for word in query.split() if word]
    length_score = min(len(words) / 40, 1.0)
    sentences = [part for part in re.split(r"[.!?]+", query) if part.strip()]
    sentence_score = min(len(sentences) / 4, 1.0)
    question_type = _question_type(query)
    if top_score is None:
        confidence_gap = 0.5
    else:
        confidence_gap = min(max(1.0 - top_score, 0.0), 1.0)
    chunk_score = min(max(chunk_count, 0) / 5, 1.0)
    ambiguity = _ambiguity(query)
    score = (
        0.25 * length_score
        + 0.15 * sentence_score
        + 0.25 * question_type
        + 0.15 * confidence_gap
        + 0.10 * chunk_score
        + 0.10 * ambiguity
    )
    return min(max(score, 0.0), 1.0)


def estimate_cost(input_tokens: int, output_tokens: int, decision: RouteDecision) -> float:
    """USD from the routed model's input and output prices per 1,000,000 tokens."""
    input_cost = input_tokens / 1_000_000 * decision.input_price
    output_cost = output_tokens / 1_000_000 * decision.output_price
    return input_cost + output_cost


def _question_type(query: str) -> float:
    lowered = f" {query.lower()} "
    if any(phrase in lowered for phrase in _COMPLEX_PHRASES):
        return 1.0
    if query.strip().endswith("?"):
        return 0.2
    return 0.0


def _ambiguity(query: str) -> float:
    lowered = query.lower()
    entities = re.findall(r"\b[A-Z][a-z]{2,}\b", query)
    if "compare" in lowered or " versus " in lowered or " vs " in lowered:
        return 1.0
    if len(entities) >= 3:
        return 0.8
    if lowered.count(" and ") >= 2:
        return 0.6
    return 0.0
