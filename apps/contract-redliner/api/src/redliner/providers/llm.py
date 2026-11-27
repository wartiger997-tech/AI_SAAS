"""Provider-abstracted LLM access with schema-validated JSON output.

The interface is intentionally small: callers ask for JSON that validates
against a Pydantic model, and receive parsed output plus token usage. When no
provider key is configured, ``StubLLM`` returns schema-shaped empty results so
the API remains fully functional in CI and local development.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from redliner.config import get_settings
from redliner.observability import get_logger

logger = get_logger(__name__)
settings = get_settings()
T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class LLMResult(BaseModel):
    output: dict[str, Any]
    usage: dict[str, int] = {}
    model: str = ""


class BaseLLM(Protocol):
    async def complete_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 4096,
    ) -> tuple[T, LLMResult]: ...

    async def complete_text(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> tuple[str, LLMResult]: ...


def _extract_json(raw: str) -> dict[str, Any]:
    text = _FENCE.sub("", raw.strip())
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = min(
            (i for i in (text.find("{"), text.find("[")) if i >= 0),
            default=-1,
        )
        end = max(text.rfind("}"), text.rfind("]"))
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
    return parsed


class OpenAILLM:
    """OpenAI-compatible chat client with optional model fallback."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str,
        fallback_models: list[str] | None = None,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=settings.llm_timeout_s,
            max_retries=2,
        )
        self.models = [model, *(fallback_models or [])]
        self.model = model

    async def _create(self, **kwargs: Any) -> tuple[Any, str]:
        last_error: Exception | None = None
        for model in self.models:
            try:
                response = await self._client.chat.completions.create(model=model, **kwargs)
                return response, model
            except Exception as exc:  # noqa: BLE001 - try the next free model
                last_error = exc
                logger.warning(
                    "llm model failed",
                    extra={"context": {"model": model, "error": str(exc)}},
                )
        raise last_error or RuntimeError("no LLM model available")

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 4096,
    ) -> tuple[T, LLMResult]:
        schema_hint = json.dumps(schema.model_json_schema(), indent=2)
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"{user}\n\nReturn ONLY JSON matching this schema:\n{schema_hint}",
            },
        ]
        last_error: Exception | None = None
        for _ in range(settings.llm_max_repair_attempts + 1):
            response, model = await self._create(
                messages=messages,  # type: ignore[arg-type]
                temperature=settings.llm_temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }
            try:
                parsed = _extract_json(raw)
                return schema.model_validate(parsed), LLMResult(
                    output=parsed, usage=usage, model=model
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "That was not valid JSON for the schema. Return corrected JSON only."
                        ),
                    }
                )
        raise ValueError(f"LLM returned invalid JSON after repairs: {last_error}")

    async def complete_text(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> tuple[str, LLMResult]:
        response, model = await self._create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=settings.llm_temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        }
        return text, LLMResult(output={"text": text}, usage=usage, model=model)


class OpenRouterLLM(OpenAILLM):
    """OpenRouter adapter. Defaults to free models and can fall back."""

    def __init__(self) -> None:
        super().__init__(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
            fallback_models=settings.openrouter_model_list[1:],
        )


class StubLLM:
    """Deterministic no-op provider used when no credentials are configured."""

    model = "stub"

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 4096,
    ) -> tuple[T, LLMResult]:
        default = _stub_default(schema)
        return default, LLMResult(output=default.model_dump(), usage={}, model=self.model)

    async def complete_text(
        self, system: str, user: str, max_tokens: int = 1024
    ) -> tuple[str, LLMResult]:
        return "", LLMResult(output={}, usage={}, model=self.model)


def _stub_default(schema: type[T]) -> T:
    """Build a schema-valid default without calling a model."""
    data: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        annotation = field.annotation
        if annotation is list:
            data[name] = []
        elif annotation is dict:
            data[name] = {}
        elif annotation is int:
            data[name] = 0
        elif annotation is float:
            data[name] = 0.0
        elif annotation is bool:
            data[name] = False
        else:
            data[name] = field.default if field.default is not None else ""
    return schema.model_validate(data)


_client: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _client
    if _client is not None:
        return _client
    if settings.llm_provider == "openrouter" and settings.openrouter_api_key:
        _client = OpenRouterLLM()
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        _client = OpenAILLM(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
        )
    else:
        logger.warning("no LLM credentials configured; using deterministic stub")
        _client = StubLLM()
    return _client
