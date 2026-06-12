from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.estimates import models


def visible_estimates(db: Session, user: User):
    """Estimator видит свои; admin/viewer — все."""
    query = select(models.Estimate).order_by(models.Estimate.created_at.desc())
    if user.role == "estimator":
        query = query.where(models.Estimate.owner_id == user.id)
    return db.scalars(query).all()


def get_owned_estimate(db: Session, estimate_id: int, user: User) -> models.Estimate:
    """Смета, которую пользователь может ЧИТАТЬ, иначе 404. Estimator — только свои."""
    est = db.get(models.Estimate, estimate_id)
    if est is None:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    return est


def require_write(est: models.Estimate, user: User) -> None:
    """Estimator пишет только свои; admin — любые; viewer — нельзя."""
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Просмотр без права изменения")
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Смета не найдена")


def get_owned_section(db: Session, section_id: int, user: User) -> models.EstimateSection:
    section = db.get(models.EstimateSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    est = section.branch.estimate
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    return section


def base_branch(est: models.Estimate) -> models.EstimateBranch:
    """Единственная базовая ветка (варианты отложены)."""
    return est.branches[0]
