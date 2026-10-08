from app.config import Settings
from app.services.routing.router import RouteDecision, complexity_score, decide, estimate_cost

SHORT = "How many annual leave days does an employee get?"
COMPLEX = (
    "Why compare the Engineering leave policy versus the Sales security policy, "
    "and explain the difference between private access and public access?"
)


def test_a_short_question_uses_the_small_model() -> None:
    settings = Settings()
    score = complexity_score(SHORT, chunk_count=1, top_score=0.99)
    assert score <= settings.routing_complexity_threshold
    decision = decide(SHORT, chunks=[], settings=settings)
    assert decision.model == settings.small_model
    assert decision.input_price == settings.small_model_price


def test_a_compare_question_uses_the_large_model() -> None:
    settings = Settings()
    score = complexity_score(COMPLEX, chunk_count=3, top_score=0.4)
    assert score > settings.routing_complexity_threshold, score
    decision = decide(COMPLEX, chunks=[], settings=settings)
    assert decision.model == settings.large_model
    assert decision.input_price == settings.large_model_price


def test_cost_changes_when_prices_change() -> None:
    cheap = RouteDecision(model="small", score=0.1, input_price=1.0, output_price=2.0)
    costly = RouteDecision(model="small", score=0.1, input_price=3.0, output_price=4.0)
    assert estimate_cost(1_000_000, 1_000_000, cheap) == 3.0
    assert estimate_cost(1_000_000, 1_000_000, costly) == 7.0
