import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_org_admin, require_superuser
from app.auth.models import ROLES, User
from app.core.config import settings
from app.core.db import get_db
from app.email import sender as email_sender
from app.orgs import service
from app.orgs.models import Organization
from app.orgs.schemas import InviteIn, OrgIn, OrgOut, UpdateUserIn

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


@router.get("", response_model=list[OrgOut])
def list_orgs(db: Session = Depends(get_db), _: User = Depends(require_superuser)):
    return service.list_orgs(db)


@router.post("", response_model=OrgOut, status_code=201)
def create_org(body: OrgIn, db: Session = Depends(get_db), _: User = Depends(require_superuser)):
    if db.scalar(select(Organization).where(Organization.name == body.name)):
        raise HTTPException(status_code=409, detail="Организация с таким именем уже есть")
    org = service.create_org(db, body.name)
    return {"id": org.id, "name": org.name, "user_count": 0}


@router.patch("/{org_id}", response_model=OrgOut)
def rename_org(
    org_id: int,
    body: OrgIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    org = service.get_org(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    if body.name != org.name and db.scalar(
        select(Organization).where(Organization.name == body.name)
    ):
        raise HTTPException(status_code=409, detail="Организация с таким именем уже есть")
    org.name = body.name
    db.commit()
    return {"id": org.id, "name": org.name, "user_count": service.count_users(db, org.id)}


# ---------------------------------------------------------------------------
# User-management endpoints (org_admin scope)
# ---------------------------------------------------------------------------


@router.post("/{org_id}/users", status_code=201)
def invite_user(
    org_id: int,
    body: InviteIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_org_admin),
):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    email = str(body.email).strip().lower()
    role = body.role
    if role not in ROLES:
        raise HTTPException(status_code=422, detail="email и валидная роль обязательны")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже есть")
    u = User(email=email, role=role, status="invited", org_id=org_id, name="")
    db.add(u)
    db.commit()
    db.refresh(u)
    u.invite_token = secrets.token_urlsafe(32)
    u.invite_expires_at = datetime.now(UTC) + timedelta(days=7)
    db.commit()
    db.refresh(u)
    org = db.get(Organization, org_id)
    link = f"{settings.frontend_url}/invite/{u.invite_token}"
    email_sent = False
    try:
        email_sender.send_invite_email(db, u.email, org.name if org else "", link)
        email_sent = True
    except (email_sender.EmailNotConfigured, email_sender.EmailError):
        email_sent = False
    return {"id": u.id, "email": u.email, "role": u.role, "status": u.status,
            "email_sent": email_sent, "invite_link": link}


@router.get("/{org_id}/users")
def list_org_users(
    org_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_org_admin),
):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    rows = db.scalars(
        select(User).where(User.org_id == org_id).order_by(User.email)
    ).all()
    return [
        {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "status": u.status}
        for u in rows
    ]


@router.patch("/{org_id}/users/{uid}")
def update_org_user(
    org_id: int,
    uid: int,
    body: UpdateUserIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_org_admin),
):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    u = db.get(User, uid)
    if u is None or u.org_id != org_id:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if body.role in ROLES:
        u.role = body.role
    if body.status in ("active", "blocked"):
        u.status = body.status
    db.commit()
    db.refresh(u)
    return {"id": u.id, "email": u.email, "role": u.role, "status": u.status}


@router.post("/{org_id}/users/{uid}/resend-invite")
def resend_invite(
    org_id: int,
    uid: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_org_admin),
):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    u = db.get(User, uid)
    if u is None or u.org_id != org_id or u.status != "invited":
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    u.invite_token = secrets.token_urlsafe(32)
    u.invite_expires_at = datetime.now(UTC) + timedelta(days=7)
    db.commit()
    org = db.get(Organization, org_id)
    link = f"{settings.frontend_url}/invite/{u.invite_token}"
    email_sent = False
    try:
        email_sender.send_invite_email(db, u.email, org.name if org else "", link)
        email_sent = True
    except (email_sender.EmailNotConfigured, email_sender.EmailError):
        email_sent = False
    return {"id": u.id, "email": u.email, "status": u.status,
            "email_sent": email_sent, "invite_link": link}
