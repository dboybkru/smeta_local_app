from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_superuser
from app.auth.models import User
from app.core.db import get_db
from app.orgs import service
from app.orgs.models import Organization
from app.orgs.schemas import OrgIn, OrgOut

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
