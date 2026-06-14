"""Единый контекст для Excel/HTML/PDF. Для public режет закупку и маржу."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.models import CatalogItem
from app.estimates import models, service

LEVELS = ("full", "cover", "estimate")


def _characteristics_map(db: Session | None, est: models.Estimate) -> dict[int, dict]:
    """item_id → characteristics для позиций сметы (для показа в КП/экспорте)."""
    if db is None:
        return {}
    ids = {
        ln.item_id
        for branch in est.branches
        for section in branch.sections
        for ln in section.lines
        if ln.item_id is not None
    }
    if not ids:
        return {}
    rows = db.execute(
        select(CatalogItem.id, CatalogItem.characteristics).where(CatalogItem.id.in_(ids))
    ).all()
    return {cid: chars for cid, chars in rows if chars}


def build_export_context(
    est: models.Estimate, *, level: str = "full", public: bool = False,
    db: Session | None = None,
) -> dict:
    if level not in LEVELS:
        level = "full"
    totals = service.compute_totals(est)
    totals_by_section = {s["section_id"]: s for s in totals["sections"]}
    chars_map = _characteristics_map(db, est)

    sections_out = []
    for branch in est.branches:
        for section in branch.sections:
            st = totals_by_section.get(section.id, {})
            lines_out = []
            for ln in section.lines:
                line = {
                    "name": ln.name,
                    "unit": ln.unit,
                    "qty": ln.qty,
                    "work_price": ln.work_price,
                    "material_price": ln.material_price,
                    "characteristics": chars_map.get(ln.item_id) if ln.item_id else None,
                }
                if not public:
                    line["purchase_price_snapshot"] = ln.purchase_price_snapshot
                lines_out.append(line)
            sections_out.append({
                "name": section.name,
                "lines": lines_out,
                "totals": _section_totals(st, public),
            })

    return {
        "object_name": est.object_name,
        "vat_enabled": est.vat_enabled,
        "vat_rate": est.vat_rate,
        "level": level,
        "public": public,
        "proposal": est.proposal or {},
        "sections": sections_out,
        "totals": _estimate_totals(totals, public),
    }


def _section_totals(st: dict, public: bool) -> dict:
    return {
        "materials": st.get("materials"),
        "works": st.get("works"),
        "total": st.get("total"),
        "purchase": None if public else st.get("purchase"),
        "margin": None if public else st.get("margin"),
    }


def _estimate_totals(totals: dict, public: bool) -> dict:
    return {
        "materials": totals["materials"],
        "works": totals["works"],
        "subtotal": totals["subtotal"],
        "vat": totals["vat"],
        "total": totals["total"],
        "purchase": None if public else totals["purchase"],
        "margin": None if public else totals["margin"],
    }
