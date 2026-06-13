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


def _strengths(m: dict) -> str:
    """Краткое описание модели из провайдерского /models (description/name), обрезанное."""
    s = m.get("description") or m.get("name") or ""
    return str(s).strip()[:300]


def _auth_headers(provider: AIProvider) -> dict[str, str]:
    key = crypto.decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else ""
    if provider.auth_style == "x_api_key":
        return {"X-Api-Key": key}
    return {"Authorization": f"Bearer {key}"}


def _base(provider: AIProvider) -> str:
    return provider.base_url.rstrip("/")


def _extract_cost(data: dict, usage: dict) -> Decimal | None:
    """Фактическая стоимость запроса в рублях (best-effort). AITunnel: cost_rub;
    другие могут класть её в usage.cost_rub/usage.cost. Если нет — None."""
    for raw in (data.get("cost_rub"), usage.get("cost_rub"), usage.get("cost")):
        if raw is None:
            continue
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError, TypeError):
            continue
    return None


def chat_completion(
    provider: AIProvider,
    model_id: str,
    messages: list[dict],
    *,
    max_tokens: int = 2000,
    json_mode: bool = False,
    http: httpx.Client | None = None,
) -> dict:
    """POST /chat/completions к OpenAI-совместимому провайдеру. http — DI для тестов.

    Возвращает {"content": str, "prompt_tokens": int, "completion_tokens": int,
    "cost_rub": Decimal|None}."""
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
        usage = data.get("usage") or {}
        return {
            "content": data["choices"][0]["message"]["content"],
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "cost_rub": _extract_cost(data, usage),
        }
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()


def list_models(provider: AIProvider, *, http: httpx.Client | None = None) -> list[dict]:
    """GET /models → список моделей с ценами (best-effort) для автоимпорта в каталог.

    Возвращает [{"id", "input_price", "output_price", "strengths"}].
    Цены парсятся из `pricing.{prompt,completion}` как есть (в единицах провайдера);
    если провайдер их не отдаёт или значение вне диапазона колонки — None.
    strengths — из `description`/`name` модели (обрезано)."""
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
                    "strengths": _strengths(m),
                }
            )
        return out
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()
