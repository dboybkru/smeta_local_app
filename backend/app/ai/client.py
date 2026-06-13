from decimal import Decimal, InvalidOperation

import httpx

from app.ai import crypto
from app.ai.errors import AIError
from app.ai.models import AIProvider

_TIMEOUT = 60.0


def _per_million(raw: object) -> Decimal | None:
    """OpenRouter-стиль: pricing.prompt/completion — цена за 1 токен (строка).
    Переводим в цену за 1M токенов. Best-effort: при любой ошибке — None."""
    if raw is None:
        return None
    try:
        return Decimal(str(raw)) * 1_000_000
    except (InvalidOperation, ValueError, TypeError):
        return None


def _auth_headers(provider: AIProvider) -> dict[str, str]:
    key = crypto.decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else ""
    if provider.auth_style == "x_api_key":
        return {"X-Api-Key": key}
    return {"Authorization": f"Bearer {key}"}


def _base(provider: AIProvider) -> str:
    return provider.base_url.rstrip("/")


def chat_completion(
    provider: AIProvider,
    model_id: str,
    messages: list[dict],
    *,
    max_tokens: int = 2000,
    json_mode: bool = False,
    http: httpx.Client | None = None,
) -> str:
    """POST /chat/completions к OpenAI-совместимому провайдеру. http — DI для тестов."""
    body: dict = {"model": model_id, "messages": messages, "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    owns = http is None
    http = http or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = http.post(
            f"{_base(provider)}/chat/completions",
            headers=_auth_headers(provider),
            json=body,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()


def list_models(provider: AIProvider, *, http: httpx.Client | None = None) -> list[dict]:
    """GET /models → список моделей с ценами (best-effort) для автоимпорта в каталог.

    Возвращает [{"id": str, "input_price": Decimal|None, "output_price": Decimal|None}].
    Цены парсятся из OpenRouter-стиля `pricing.{prompt,completion}` (за 1 токен → за 1M);
    если провайдер их не отдаёт — None."""
    owns = http is None
    http = http or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = http.get(
            f"{_base(provider)}/models", headers=_auth_headers(provider), timeout=_TIMEOUT
        )
        resp.raise_for_status()
        out: list[dict] = []
        for m in resp.json().get("data", []):
            pricing = m.get("pricing") or {}
            out.append(
                {
                    "id": m["id"],
                    "input_price": _per_million(pricing.get("prompt")),
                    "output_price": _per_million(pricing.get("completion")),
                }
            )
        return out
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()
