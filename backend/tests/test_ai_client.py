import httpx
import pytest

from app.ai import client, crypto
from app.ai.errors import AIError
from app.ai.models import AIProvider


def _provider(auth_style="bearer"):
    return AIProvider(
        name="p", base_url="https://api.example.com/v1",
        auth_style=auth_style, api_key_encrypted=crypto.encrypt("sk-test-123"),
        enabled=True,
    )


def test_chat_completion_bearer_header_and_parse():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["xapi"] = request.headers.get("x-api-key")
        captured["path"] = request.url.path
        import json as _j
        captured["body"] = _j.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi there"}}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    out = client.chat_completion(_provider("bearer"), "gpt-x",
                                 [{"role": "user", "content": "q"}],
                                 max_tokens=100, json_mode=False, http=http)
    assert out == "hi there"
    assert captured["auth"] == "Bearer sk-test-123"
    assert captured["xapi"] is None
    assert captured["path"].endswith("/chat/completions")
    assert captured["body"]["model"] == "gpt-x"
    assert "response_format" not in captured["body"]


def test_chat_completion_xapikey_and_json_mode():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["xapi"] = request.headers.get("x-api-key")
        captured["auth"] = request.headers.get("authorization")
        import json as _j
        captured["body"] = _j.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client.chat_completion(_provider("x_api_key"), "m",
                           [{"role": "user", "content": "q"}],
                           max_tokens=50, json_mode=True, http=http)
    assert captured["xapi"] == "sk-test-123"
    assert captured["auth"] is None
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_chat_completion_http_error_raises_aierror():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AIError):
        client.chat_completion(_provider(), "m", [{"role": "user", "content": "q"}],
                               max_tokens=10, json_mode=False, http=http)


def test_list_models_parses_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "gpt-x"}, {"id": "claude-y"}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    models = client.list_models(_provider(), http=http)
    assert [m["id"] for m in models] == ["gpt-x", "claude-y"]
    assert models[0]["input_price"] is None and models[0]["output_price"] is None


def test_list_models_parses_pricing_raw_with_guard():
    from decimal import Decimal

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {"id": "ok", "pricing": {"prompt": "0.15", "completion": "0.6"}},
            {"id": "overflow", "pricing": {"prompt": "999999999", "completion": "0.6"}},
            {"id": "no-price", "pricing": {}},
        ]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    models = client.list_models(_provider(), http=http)
    # хранится как есть, без масштабирования
    assert models[0]["input_price"] == Decimal("0.15")
    assert models[0]["output_price"] == Decimal("0.6")
    # значение >= 10^8 не влезает в Numeric(12,4) → None (не падаем)
    assert models[1]["input_price"] is None
    assert models[1]["output_price"] == Decimal("0.6")
    assert models[2]["input_price"] is None and models[2]["output_price"] is None


def test_list_models_parses_strengths_from_description():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {"id": "a", "description": "Fast and cheap"},
            {"id": "b", "name": "Big model"},
            {"id": "c"},
        ]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    models = client.list_models(_provider(), http=http)
    assert models[0]["strengths"] == "Fast and cheap"
    assert models[1]["strengths"] == "Big model"
    assert models[2]["strengths"] == ""
