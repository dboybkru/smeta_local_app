import secrets

from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"


def set_auth_cookies(response: Response, access: str, refresh: str) -> str:
    """Ставит access/refresh (httpOnly) + csrf (JS-видимый). Возвращает csrf-токен."""
    csrf = secrets.token_urlsafe(32)
    secure = settings.cookie_secure
    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=secure, samesite="lax",
        path="/api", max_age=settings.access_token_ttl_minutes * 60,
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh, httponly=True, secure=secure, samesite="lax",
        path="/api/auth", max_age=settings.refresh_token_ttl_days * 86400,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="lax",
        path="/", max_age=settings.refresh_token_ttl_days * 86400,
    )
    return csrf


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")
