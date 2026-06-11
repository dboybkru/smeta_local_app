from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.schemas import LoginIn, RegisterIn, TokenPair, UserOut
from app.core.db import get_db

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
