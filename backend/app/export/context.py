"""Единый контекст для Excel/HTML/PDF. Для public режет закупку и маржу."""
from app.estimates import models, service

LEVELS = ("full", "cover", "estimate")


def build_export_context(
    est: models.Estimate, *, level: str = "full", public: bool = False
) -> dict:
    if level not in LEVELS:
        level = "full"
    totals = service.compute_totals(est)
    totals_by_section = {s["section_id"]: s for s in totals["sections"]}

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
