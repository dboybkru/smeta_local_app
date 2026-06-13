from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client, crypto, router_advisor, schemas, service
from app.ai.errors import AIError, AINotConfigured
from app.ai.models import AIModel, AIProvider, AIPurpose
from app.auth.deps import require_admin
from app.auth.models import User
from app.core.db import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _provider_out(p: AIProvider) -> schemas.ProviderOut:
    return schemas.ProviderOut(
        id=p.id, name=p.name, base_url=p.base_url, auth_style=p.auth_style,
        enabled=p.enabled, has_key=bool(p.api_key_encrypted),
    )


# --- providers ---
@router.get("/providers", response_model=list[schemas.ProviderOut])
def list_providers(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return [_provider_out(p) for p in db.scalars(select(AIProvider).order_by(AIProvider.id)).all()]


@router.post("/providers", response_model=schemas.ProviderOut, status_code=201)
def create_provider(
    body: schemas.ProviderIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = AIProvider(
        name=body.name, base_url=body.base_url, auth_style=body.auth_style,
        api_key_encrypted=crypto.encrypt(body.api_key) if body.api_key else "",
        enabled=body.enabled,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _provider_out(p)


@router.put("/providers/{provider_id}", response_model=schemas.ProviderOut)
def update_provider(
    provider_id: int,
    body: schemas.ProviderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = db.get(AIProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    data = body.model_dump(exclude_unset=True)
    if "api_key" in data:
        key = data.pop("api_key")
        if key:
            p.api_key_encrypted = crypto.encrypt(key)
    for field, value in data.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _provider_out(p)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = db.get(AIProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    db.delete(p)
    db.commit()


# --- models (catalog) ---
@router.post("/providers/{provider_id}/models/refresh")
def refresh_models(
    provider_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = db.get(AIProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    existing = {
        m.model_id: m
        for m in db.scalars(select(AIModel).where(AIModel.provider_id == p.id)).all()
    }
    imported = 0
    updated = 0
    for m in client.list_models(p):
        mid = m["id"]
        if mid in existing:
            # backfill цен у уже импортированных моделей (только если были пустые)
            em = existing[mid]
            changed = False
            if em.input_price is None and m.get("input_price") is not None:
                em.input_price = m["input_price"]
                changed = True
            if em.output_price is None and m.get("output_price") is not None:
                em.output_price = m["output_price"]
                changed = True
            if changed:
                updated += 1
            continue
        new_m = AIModel(
            provider_id=p.id, model_id=mid, label=mid,
            input_price=m.get("input_price"), output_price=m.get("output_price"),
        )
        db.add(new_m)
        existing[mid] = new_m
        imported += 1
    db.commit()
    return {"imported": imported, "updated": updated}


@router.get("/models", response_model=list[schemas.ModelOut])
def list_models(
    provider_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    q = select(AIModel).order_by(AIModel.id)
    if provider_id is not None:
        q = q.where(AIModel.provider_id == provider_id)
    return db.scalars(q).all()


@router.put("/models/{model_id}", response_model=schemas.ModelOut)
def update_model(
    model_id: int,
    body: schemas.ModelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    m = db.get(AIModel, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/models/{model_id}", status_code=204)
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    m = db.get(AIModel, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    db.delete(m)
    db.commit()


# --- purposes ---
@router.get("/purposes", response_model=list[schemas.PurposeOut])
def list_purposes(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return db.scalars(select(AIPurpose).order_by(AIPurpose.id)).all()


@router.put("/purposes/{key}", response_model=schemas.PurposeOut)
def update_purpose(
    key: str,
    body: schemas.PurposeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    purpose = db.scalars(select(AIPurpose).where(AIPurpose.key == key)).first()
    if purpose is None:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(purpose, field, value)
    db.commit()
    db.refresh(purpose)
    return purpose


# --- router advisor ---
@router.post("/router/recommend", response_model=list[schemas.Recommendation])
def router_recommend(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        return router_advisor.recommend_models(db)
    except AINotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# --- purpose smoke test ---
@router.post("/purposes/{key}/test")
def test_purpose(
    key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        service.call_llm(db, key, [{"role": "user", "content": "ping"}], max_tokens=16)
        return {"ok": True, "detail": ""}
    except (AINotConfigured, AIError) as exc:
        return {"ok": False, "detail": str(exc)}
