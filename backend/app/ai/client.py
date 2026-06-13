from decimal import Decimal, InvalidOperation

import httpx

from app.ai import crypto
from app.ai.errors import AIError
from app.ai.models import AIProvider

_TIMEOUT = 60.0


_PRICE_MAX = Decimal("100000000")  # Numeric(12,4): |v| должно быть < 10^8


def _parse_price(raw: object) -> Decimal | None:
    """Цена модели из провайдерского /models (в единицах провайдера — как есть).
    Best-effort: при невалидном значении или выходе за диапазон колонки → None
    (НЕ масштабируем: у VseGPT/AITunnel это не цена за 1 токен, ×1e6 даёт overflow)."""
    if raw is None:
        return None
    try:
        v = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if v < 0 or v >= _PRICE_MAX:
        return None
    return v


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
    Цены парсятся из `pricing.{prompt,completion}` как есть (в единицах провайдера);
    если провайдер их не отдаёт или значение вне диапазона колонки — None."""
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
                    "input_price": _parse_price(pricing.get("prompt")),
                    "output_price": _parse_price(pricing.get("completion")),
                }
            )
        return out
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()
