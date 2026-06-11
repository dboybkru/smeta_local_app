from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginIn, RefreshIn, RegisterIn, TokenPair, UserOut
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
