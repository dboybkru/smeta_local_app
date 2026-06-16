from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_superuser
from app.auth.models import User
from app.auth.schemas import UserOut
from app.core.db import get_db

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_superuser)]
)


class StatusIn(BaseModel):
    status: Literal["active", "blocked"]


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.created_at)).all()


@router.post("/users/{user_id}/status", response_model=UserOut)
def set_status(
    user_id: int,
    body: StatusIn,
    db: Session = Depends(get_db),
    # require_superuser выполняется и на уровне роутера, и здесь (FastAPI кэширует
    # по identity Depends-объекта, так что это второй прогон цепочки — осознанно:
    # нам нужен сам объект superuser). Накладные расходы малы.
    superuser: User = Depends(require_superuser),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == superuser.id and body.status == "blocked":
        raise HTTPException(status_code=400, detail="Нельзя заблокировать самого себя")
    user.status = body.status
    db.commit()
    db.refresh(user)
    return user
