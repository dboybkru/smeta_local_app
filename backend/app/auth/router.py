import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import service, yandex
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginIn, RefreshIn, RegisterIn, TokenPair, UserOut
from app.core.config import settings
from app.core.db import get_db
from app.core.security import InvalidTokenError, decode_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    try:
        return service.register_user(db, body.email, body.password, body.name)
    except service.EmailTakenError:
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)):
    try:
        user = service.authenticate(db, body.email, body.password)
    except service.InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    return service.issue_tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Недействительный refresh-токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, int(payload["sub"]))
    if user is None or user.status == "blocked":
        raise HTTPException(
            status_code=401,
            detail="Недействительный refresh-токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return service.issue_tokens(user)


@router.get("/yandex/login")
def yandex_login():
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(yandex.build_authorize_url(state))
    resp.set_cookie("yx_state", state, max_age=600, httponly=True, samesite="lax")
    return resp


@router.get("/yandex/callback")
def yandex_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    if not state or state != request.cookies.get("yx_state"):
        raise HTTPException(status_code=400, detail="Неверный state")
    token = yandex.exchange_code(code)
    info = yandex.fetch_userinfo(token)
    user = service.get_or_create_yandex_user(db, info)
    if user.status == "blocked":
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    pair = service.issue_tokens(user)
    url = (
        f"{settings.frontend_url}/auth/callback"
        f"#access_token={pair['access_token']}&refresh_token={pair['refresh_token']}"
    )
    resp = RedirectResponse(url)
    resp.delete_cookie("yx_state")
    return resp
