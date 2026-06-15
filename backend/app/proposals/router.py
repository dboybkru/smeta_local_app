from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.errors import AIError, AINotConfigured
from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import service as est_service
from app.profile import service as profile_service
from app.proposals import schemas, service

router = APIRouter(prefix="/api", tags=["proposals"])


@router.post("/estimates/{estimate_id}/proposal/generate")
def generate(
    estimate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    profile = profile_service.get_profile(db, est.org_id)
    try:
        blocks = service.generate_proposal(db, est, profile)
    except AINotConfigured:
        raise HTTPException(status_code=503, detail="AI не настроен")
    except AIError as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка AI: {exc}")
    est.proposal = blocks
    db.commit()
    return blocks


@router.patch("/estimates/{estimate_id}/proposal")
def patch_proposal(
    estimate_id: int,
    body: schemas.ProposalPatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    current = dict(est.proposal or {})
    current.update(body.model_dump(exclude_unset=True))
    est.proposal = current
    db.commit()
    return current
