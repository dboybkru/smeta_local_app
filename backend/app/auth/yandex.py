import httpx

from app.core.config import settings

AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"
USERINFO_URL = "https://login.yandex.ru/info"


def build_authorize_url(state: str) -> str:
    from urllib.parse import urlencode

    params = urlencode(
        {
            "response_type": "code",
            "client_id": settings.yandex_client_id,
            "redirect_uri": f"{settings.backend_url}/api/auth/yandex/callback",
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{params}"


def exchange_code(code: str) -> str:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.yandex_client_id,
            "client_secret": settings.yandex_client_secret,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_userinfo(access_token: str) -> dict:
    resp = httpx.get(
        USERINFO_URL,
        params={"format": "json"},
        headers={"Authorization": f"OAuth {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()
