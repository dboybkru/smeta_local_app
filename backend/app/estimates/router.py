from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.catalog.models import CatalogItem
from app.clients import dadata
from app.core.db import get_db
from app.estimates import models, schemas, service
from app.settings import service as settings_service

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
    user: User = Depends(require_active),
):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Просмотр без права изменения")
    client = models.Client(**body.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/clients/suggest", dependencies=[Depends(require_active)])
def suggest_clients(q: str = "", db: Session = Depends(get_db)):
    token = settings_service.get_secret(db, "dadata_token")
    if not token:
        return []
    secret = settings_service.get_secret(db, "dadata_secret")
    return dadata.suggest_parties(token, q, secret=secret)


@router.get("/clients/{client_id}", response_model=schemas.ClientOut,
            dependencies=[Depends(require_active)])
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.get(models.Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return client


@router.patch("/clients/{client_id}", response_model=schemas.ClientOut)
def update_client(
    client_id: int, body: schemas.ClientPatch,
    db: Session = Depends(get_db), user: User = Depends(require_active),
):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Просмотр без права изменения")
    client = db.get(models.Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
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


@router.get("/estimates/{estimate_id}", response_model=schemas.EstimateDetail)
def get_estimate(
    estimate_id: int, db: Session = Depends(get_db), user: User = Depends(require_active)
):
    est = service.get_owned_estimate(db, estimate_id, user)
    return service.build_estimate_detail(est, user)


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


@router.post("/sections/{section_id}/lines", response_model=schemas.LineOut, status_code=201)
def add_line(
    section_id: int,
    body: schemas.LineIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    section = service.get_owned_section(db, section_id, user)
    service.require_write(section.branch.estimate, user)
    if body.item_id is not None:
        item = db.get(CatalogItem, body.item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Позиция каталога не найдена")
        est = section.branch.estimate
        client = db.get(models.Client, est.client_id) if est.client_id else None
        work, material, purchase = service.snapshot_line_values(db, item, client)
        line = models.EstimateLine(
            section_id=section.id,
            item_id=item.id,
            name=item.name,
            unit=item.unit,
            qty=body.qty,
            work_price=work,
            material_price=material,
            purchase_price_snapshot=purchase,
            sort_order=len(section.lines),
        )
    else:
        line = models.EstimateLine(
            section_id=section.id,
            name=body.name or "",
            unit=body.unit or "шт",
            qty=body.qty,
            work_price=body.work_price or 0,
            material_price=body.material_price or 0,
            purchase_price_snapshot=body.purchase_price_snapshot,
            sort_order=len(section.lines),
        )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.patch("/lines/{line_id}", response_model=schemas.LineOut)
def patch_line(
    line_id: int,
    body: schemas.LinePatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    line = service.get_owned_line(db, line_id, user)
    service.require_write(line.section.branch.estimate, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    db.commit()
    db.refresh(line)
    return line


@router.delete("/lines/{line_id}", status_code=204)
def delete_line(
    line_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    line = service.get_owned_line(db, line_id, user)
    service.require_write(line.section.branch.estimate, user)
    db.delete(line)
    db.commit()
