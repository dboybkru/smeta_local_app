import httpx

from app.ai import crypto
from app.ai.errors import AIError
from app.ai.models import AIProvider

_TIMEOUT = 60.0


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


def list_models(provider: AIProvider, *, http: httpx.Client | None = None) -> list[str]:
    """GET /models → список id (для автоимпорта в каталог)."""
    owns = http is None
    http = http or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = http.get(
            f"{_base(provider)}/models", headers=_auth_headers(provider), timeout=_TIMEOUT
        )
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()
