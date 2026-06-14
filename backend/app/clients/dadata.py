import httpx

_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
_TIMEOUT = 10.0


def suggest_parties(
    token: str, query: str, count: int = 10, *, secret: str = "", http: httpx.Client | None = None
) -> list[dict]:
    """Подсказки организаций/ИП от DaData. Best-effort: при любой ошибке → [].
    secret — X-Secret (нужен для Clean/balance API; для подсказок необязателен)."""
    if not token or not query.strip():
        return []
    owns = http is None
    http = http or httpx.Client(timeout=_TIMEOUT)
    try:
        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if secret:
            headers["X-Secret"] = secret
        resp = http.post(
            _URL,
            headers=headers,
            json={"query": query, "count": min(count, 20)},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        out = []
        for s in resp.json().get("suggestions", []):
            d = s.get("data", {}) or {}
            out.append({
                "value": s.get("value", ""),
                "inn": d.get("inn", ""),
                "kpp": d.get("kpp", ""),
                "ogrn": d.get("ogrn", ""),
                "name_short": (d.get("name") or {}).get("short_with_opf", ""),
                "address": (d.get("address") or {}).get("value", ""),
                "management": (d.get("management") or {}).get("name", ""),
                "type": d.get("type", ""),
                "status": (d.get("state") or {}).get("status", ""),
            })
        return out
    except (httpx.HTTPError, ValueError, KeyError):
        return []
    finally:
        if owns:
            http.close()
