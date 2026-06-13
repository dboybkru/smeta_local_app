from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import service as est_service
from app.export import context as ctx
from app.export import render
from app.export.excel import render_xlsx

router = APIRouter(prefix="/api", tags=["export"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/estimates/{estimate_id}/export.xlsx")
def export_xlsx(
    estimate_id: int,
    level: str = "full",
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    context = ctx.build_export_context(est, level=level, public=False)
    data = render_xlsx(context)
    return Response(
        content=data,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="estimate-{est.id}.xlsx"'},
    )


@router.get("/estimates/{estimate_id}/export.pdf")
def export_pdf(
    estimate_id: int,
    level: str = "full",
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    context = ctx.build_export_context(est, level=level, public=False)
    html = render.render_html(context)
    pdf = render.html_to_pdf(html)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estimate-{est.id}.pdf"'},
    )
