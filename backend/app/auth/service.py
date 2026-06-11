from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


class EmailTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def register_user(db: Session, email: str, password: str, name: str) -> User:
    if db.scalar(select(User).where(User.email == email)):
        raise EmailTakenError(email)
    is_first = (db.scalar(select(func.count()).select_from(User)) or 0) == 0
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        role="admin" if is_first else "estimator",
        status="active" if is_first else "pending",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError(email)
    return user


def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.role),
        "token_type": "bearer",
    }
