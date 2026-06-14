from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.errors import AIError, AINotConfigured
from app.assistant import schemas, service
from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import schemas as est_schemas
from app.estimates import service as est_service

router = APIRouter(prefix="/api", tags=["assistant"])


@router.get(
    "/estimates/{estimate_id}/assistant/messages",
    response_model=list[schemas.AssistantMessageOut],
)
def assistant_messages(
    estimate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    return service.load_history(db, est.id)


@router.post("/estimates/{estimate_id}/assistant/chat", response_model=schemas.ChatResponse)
def assistant_chat(
    estimate_id: int,
    body: schemas.ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    history = service.load_history(db, est.id)
    convo = [*history, schemas.ChatMessage(role="user", content=body.message)]
    try:
        resp = service.run_assistant(db, est, convo)
    except AINotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    # сохраняем диалог только после успешного ответа AI
    service.save_message(db, est.id, "user", body.message)
    service.save_message(db, est.id, "assistant", resp.reply)
    return resp


@router.post(
    "/estimates/{estimate_id}/assistant/apply",
    response_model=est_schemas.EstimateDetail,
)
def assistant_apply(
    estimate_id: int,
    body: schemas.ApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    try:
        service.apply_changeset(db, est, body.operations)
    except service.ApplyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    service.save_message(db, est.id, "assistant", "✓ Изменения применены.")
    db.refresh(est)
    return est_service.build_estimate_detail(est, user)
