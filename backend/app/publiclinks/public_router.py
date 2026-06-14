from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.estimates import models as est_models
from app.export import context as ctx
from app.export import render
from app.publiclinks import service

router = APIRouter(tags=["public"])


def _context_for_link(db: Session, token: str) -> tuple[dict, str]:
    link = service.resolve_token(db, token)
    est = db.get(est_models.Estimate, link.estimate_id)
    if est is None:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    context = ctx.build_export_context(est, level=link.level, public=True, db=db)
    watermark = link.watermark_text if link.watermark_enabled else ""
    return context, watermark


@router.get("/p/{token}", response_class=HTMLResponse)
def public_page(token: str, db: Session = Depends(get_db)):
    context, watermark = _context_for_link(db, token)
    return HTMLResponse(render.render_html(context, watermark=watermark))


@router.get("/p/{token}/pdf")
def public_pdf(token: str, db: Session = Depends(get_db)):
    context, watermark = _context_for_link(db, token)
    html = render.render_html(context, watermark=watermark)
    pdf = render.html_to_pdf(html)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="proposal.pdf"'},
    )
