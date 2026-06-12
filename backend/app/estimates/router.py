from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import models, schemas, service

router = APIRouter(prefix="/api", tags=["estimates"])


@router.get(
    "/clients",
    response_model=list[schemas.ClientOut],
    dependencies=[Depends(require_active)],
)
def list_clients(db: Session = Depends(get_db)):
    return db.scalars(select(models.Client).order_by(models.Client.name)).all()


@router.post("/clients", response_model=schemas.ClientOut, status_code=201)
def create_client(
    body: schemas.ClientIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_active),
):
    client = models.Client(name=body.name, default_price_level_id=body.default_price_level_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/estimates", response_model=list[schemas.EstimateOut])
def list_estimates(db: Session = Depends(get_db), user: User = Depends(require_active)):
    return service.visible_estimates(db, user)


@router.post("/estimates", response_model=schemas.EstimateOut, status_code=201)
def create_estimate(
    body: schemas.EstimateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Просмотр без права изменения")
    est = models.Estimate(
        owner_id=user.id,
        object_name=body.object_name,
        client_id=body.client_id,
        vat_enabled=body.vat_enabled,
        vat_rate=body.vat_rate,
    )
    est.branches.append(models.EstimateBranch(name="Базовая"))
    db.add(est)
    db.commit()
    db.refresh(est)
    return est


@router.get("/estimates/{estimate_id}", response_model=schemas.EstimateOut)
def get_estimate(
    estimate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    return service.get_owned_estimate(db, estimate_id, user)


@router.patch("/estimates/{estimate_id}", response_model=schemas.EstimateOut)
def patch_estimate(
    estimate_id: int,
    body: schemas.EstimatePatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = service.get_owned_estimate(db, estimate_id, user)
    service.require_write(est, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(est, field, value)
    db.commit()
    db.refresh(est)
    return est


@router.delete("/estimates/{estimate_id}", status_code=204)
def delete_estimate(
    estimate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = service.get_owned_estimate(db, estimate_id, user)
    service.require_write(est, user)
    db.delete(est)
    db.commit()


@router.post(
    "/estimates/{estimate_id}/sections",
    response_model=schemas.SectionOut,
    status_code=201,
)
def add_section(
    estimate_id: int,
    body: schemas.SectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = service.get_owned_estimate(db, estimate_id, user)
    service.require_write(est, user)
    branch = service.base_branch(est)
    section = models.EstimateSection(
        branch_id=branch.id,
        name=body.name,
        markup_percent=body.markup_percent,
        sort_order=len(branch.sections),
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.patch("/sections/{section_id}", response_model=schemas.SectionOut)
def patch_section(
    section_id: int,
    body: schemas.SectionPatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    section = service.get_owned_section(db, section_id, user)
    service.require_write(section.branch.estimate, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(section, field, value)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/sections/{section_id}", status_code=204)
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    section = service.get_owned_section(db, section_id, user)
    service.require_write(section.branch.estimate, user)
    db.delete(section)
    db.commit()
