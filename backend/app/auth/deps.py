from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.db import get_db
from app.core.security import InvalidTokenError, decode_token

_bearer = HTTPBearer(auto_error=False)

_WWW = {"WWW-Authenticate": "Bearer"}


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Нет токена", headers=_WWW)
    try:
        payload = decode_token(creds.credentials, expected_type="access")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный токен", headers=_WWW)
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден", headers=_WWW)
    return user


def require_active(user: User = Depends(get_current_user)) -> User:
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Аккаунт не активирован")
    return user


def require_admin(user: User = Depends(require_active)) -> User:
    if not (user.is_superuser or user.role == "org_admin"):
        raise HTTPException(status_code=403, detail="Нужны права администратора")
    return user


def require_superuser(user: User = Depends(require_active)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Нужны права суперпользователя")
    return user


def current_org(user: User = Depends(require_active)) -> int:
    if user.org_id is None:
        raise HTTPException(
            status_code=403, detail="Аккаунт не привязан к организации"
        )
    return user.org_id


def require_org_admin(user: User = Depends(require_active)) -> User:
    if not (user.is_superuser or user.role == "org_admin"):
        raise HTTPException(status_code=403, detail="Нужны права администратора организации")
    return user
