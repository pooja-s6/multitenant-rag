import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings
from app.services.exceptions import BadGateway, BadRequest
from app.services.retrieval.search import RetrievedChunk


@dataclass(frozen=True)
class LLMResult:
    answer: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMProvider(Protocol):
    def complete(
        self,
        *,
        system: str,
        user: str,
        chunks: list[RetrievedChunk],
        model: str | None = None,
    ) -> LLMResult:
        """Return an answer grounded in the retrieved chunks."""


class FakeLLMProvider:
    """Answers from retrieved text so tests never call an external model."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def complete(
        self,
        *,
        system: str,
        user: str,
        chunks: list[RetrievedChunk],
        model: str | None = None,
    ) -> LLMResult:
        if not chunks:
            answer = "I could not find that in the documents you can access."
        else:
            top = chunks[0]
            answer = f"Based on {top.filename}: {top.content}"
        return LLMResult(
            answer=answer,
            model=model or self.model_name,
            input_tokens=_token_count(system) + _token_count(user),
            output_tokens=_token_count(answer),
        )


class OpenAICompatibleProvider:
    """Calls a chat-completions endpoint. The caller chooses the model name."""

    def __init__(self, *, model_name: str, api_key: str, base_url: str, timeout_seconds: float = 60) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        *,
        system: str,
        user: str,
        chunks: list[RetrievedChunk],
        model: str | None = None,
    ) -> LLMResult:
        del chunks
        chosen = model or self.model_name
        payload = {
            "model": chosen,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise BadGateway("The language model request failed.") from exc
        try:
            answer = str(body["choices"][0]["message"]["content"]).strip()
            usage = body.get("usage") or {}
            return LLMResult(
                answer=answer or "I could not find that in the documents you can access.",
                model=str(body.get("model") or chosen),
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise BadGateway("The language model returned an unexpected response.") from exc


def get_llm_provider() -> LLMProvider:
    from app.config import get_settings

    return provider_for(get_settings())


def provider_for(settings: Settings) -> LLMProvider:
    """An empty API key always uses the fake provider."""
    name = settings.llm_provider.strip().lower()
    if name == "fake" or not settings.llm_api_key.strip():
        return FakeLLMProvider(settings.small_model)
    if name == "openai":
        return OpenAICompatibleProvider(
            model_name=settings.small_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    raise BadRequest(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'.")


def _token_count(text: str) -> int:
    words = [word for word in text.split() if word]
    return max(len(words), 1)
