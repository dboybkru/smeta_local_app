from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)

# Реальный argon2-хеш одноразовой строки: используется для выравнивания времени ответа
# в пути «email не найден», чтобы нельзя было перебрать email по таймингу.
_DUMMY_HASH = hash_password("timing-equalizer-dummy")


class EmailTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def register_user(db: Session, email: str, password: str, name: str) -> User:
    if db.scalar(select(User).where(User.email == email)):
        raise EmailTakenError(email)
    # Гонка двух первых регистраций не закрыта на уровне БД —
    # приемлемо: оператор регистрируется первым при деплое.
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
    # Хеш проверяется всегда, чтобы по времени ответа нельзя было перебрать email.
    # Пользователь без password_hash (Яндекс-аккаунт) никогда не проходит,
    # даже если verify_password вернёт True против dummy-хеша.
    if user and user.password_hash:
        valid = verify_password(password, user.password_hash)
    else:
        # Прогоняем verify для выравнивания времени; результат отбрасываем.
        verify_password(password, _DUMMY_HASH)
        valid = False
    if not valid:
        raise InvalidCredentialsError(email)
    if user.status == "blocked":
        raise InvalidCredentialsError(email)
    return user


def get_or_create_yandex_user(db: Session, info: dict) -> User:
    yandex_id = str(info["id"])
    email = info.get("default_email") or f"{yandex_id}@yandex.local"
    user = db.scalar(select(User).where(User.yandex_id == yandex_id))
    if user:
        return user
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.yandex_id = yandex_id
        db.commit()
        db.refresh(user)
        return user
    is_first = (db.scalar(select(func.count()).select_from(User)) or 0) == 0
    user = User(
        email=email,
        yandex_id=yandex_id,
        name=info.get("real_name") or "",
        role="admin" if is_first else "estimator",
        status="active" if is_first else "pending",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_tokens(user: User) -> dict[str, str]:
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.role),
        "token_type": "bearer",
    }
