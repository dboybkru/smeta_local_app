import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import service, yandex
from app.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginIn, RefreshIn, RegisterIn, UserOut
from app.core.config import settings
from app.core.db import get_db
from app.core.security import InvalidTokenError, decode_token
from app.orgs.models import Organization
from app.settings import service as settings_service
from app.settings.router import YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _yandex_creds(db: Session) -> tuple[str, str]:
    """Возвращает (client_id, client_secret): DB-значение или env-фолбэк."""
    client_id = settings_service.get_secret(db, YANDEX_CLIENT_ID) or settings.yandex_client_id
    client_secret = (
        settings_service.get_secret(db, YANDEX_CLIENT_SECRET) or settings.yandex_client_secret
    )
    return client_id, client_secret


def _user_out(db: Session, user: User) -> UserOut:
    org_name: str | None = None
    if user.org_id is not None:
        org = db.get(Organization, user.org_id)
        if org is not None:
            org_name = org.name
    return UserOut(
        id=user.id, email=user.email, name=user.name, role=user.role,
        status=user.status, is_superuser=user.is_superuser,
        org_id=user.org_id, org_name=org_name,
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = service.register_user(db, body.email, body.password, body.name)
    except service.EmailTakenError:
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")
    if user.status == "active":
        t = service.issue_tokens(user)
        set_auth_cookies(response, t["access_token"], t["refresh_token"])
    return _user_out(db, user)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = service.authenticate(db, body.email, body.password)
    except service.InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    t = service.issue_tokens(user)
    set_auth_cookies(response, t["access_token"], t["refresh_token"])
    return _user_out(db, user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _user_out(db, user)


@router.post("/refresh", response_model=UserOut)
def refresh(
    request: Request,
    response: Response,
    body: RefreshIn | None = None,
    db: Session = Depends(get_db),
):
    token = request.cookies.get("refresh_token") or (body.refresh_token if body else None)
    if not token:
        raise HTTPException(status_code=401, detail="Нет refresh-токена",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(token, expected_type="refresh")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен",
                            headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, int(payload["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен",
                            headers={"WWW-Authenticate": "Bearer"})
    t = service.issue_tokens(user)
    set_auth_cookies(response, t["access_token"], t["refresh_token"])
    return _user_out(db, user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_auth_cookies(response)


@router.get("/config")
def auth_config(db: Session = Depends(get_db)):
    cid, _ = _yandex_creds(db)
    return {"yandex_enabled": bool(cid)}


@router.get("/yandex/login")
def yandex_login(db: Session = Depends(get_db)):
    cid, _ = _yandex_creds(db)
    if not cid:
        raise HTTPException(status_code=503, detail="Вход через Яндекс не настроен")
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(yandex.build_authorize_url(state, cid))
    resp.set_cookie(
        "yx_state", state, max_age=600, httponly=True,
        samesite="lax", secure=settings.cookie_secure,
    )
    return resp


@router.get("/yandex/callback")
def yandex_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    if state != request.cookies.get("yx_state"):
        raise HTTPException(status_code=400, detail="Неверный state")
    cid, secret = _yandex_creds(db)
    try:
        token = yandex.exchange_code(code, cid, secret)
        info = yandex.fetch_userinfo(token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Ошибка авторизации через Яндекс") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Яндекс недоступен") from exc
    user = service.get_or_create_yandex_user(db, info)
    if user.status == "blocked":
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    t = service.issue_tokens(user)
    resp = RedirectResponse(f"{settings.frontend_url}/auth/callback")
    set_auth_cookies(resp, t["access_token"], t["refresh_token"])
    resp.delete_cookie("yx_state")
    return resp
