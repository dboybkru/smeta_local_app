from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.orgs.models import Organization
from app.publiclinks import public_router
from app.publiclinks.models import PublicLink


def _estimate_with_link(db_session, **link_kwargs):
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    u = User(email="u@x.ru", name="U", role="estimator", status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, org_id=org.id, object_name="Объект Икс")
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Кровля", markup_percent=0)
    section.lines.append(
        EstimateLine(name="Монтаж кровли", unit="м²", qty=30, work_price=600,
                     material_price=400, purchase_price_snapshot=333)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    link = PublicLink(estimate_id=est.id, token=link_kwargs.pop("token", "tok-ok"), **link_kwargs)
    db_session.add(link)
    db_session.commit()
    return est, link


def test_public_page_ok_and_no_margin_purchase(client, db_session):
    est, link = _estimate_with_link(db_session, level="full")
    r = client.get(f"/p/{link.token}")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "Объект Икс" in body
    assert "Монтаж кровли" in body
    assert "Маржа" not in body
    assert "Закупка" not in body
    assert "333" not in body  # закупочная цена не утекла


def test_public_revoked_404(client, db_session):
    est, link = _estimate_with_link(db_session, token="tok-revoked", revoked=True)
    assert client.get(f"/p/{link.token}").status_code == 404


def test_public_expired_410(client, db_session):
    est, link = _estimate_with_link(
        db_session, token="tok-exp", expires_at=datetime.now(UTC) - timedelta(days=1)
    )
    assert client.get(f"/p/{link.token}").status_code == 410


def test_public_unknown_404(client):
    assert client.get("/p/does-not-exist").status_code == 404


def test_public_watermark_present(client, db_session):
    est, link = _estimate_with_link(
        db_session, token="tok-wm", watermark_enabled=True, watermark_text="ЧЕРНОВИК"
    )
    assert "ЧЕРНОВИК" in client.get(f"/p/{link.token}").text


def test_public_pdf_ok_and_no_leak_in_html(client, db_session, monkeypatch):
    est, link = _estimate_with_link(db_session, token="tok-pdf")
    # spy: захватываем HTML, который уходит в рендер PDF — закупка не должна туда попасть
    captured = {}
    monkeypatch.setattr(
        public_router.render,
        "html_to_pdf",
        lambda html: (captured.__setitem__("html", html) or b"%PDF-1.7 mock"),
    )
    r = client.get(f"/p/{link.token}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "333" not in captured["html"]  # закупочная цена не утекла в PDF
    assert "Маржа" not in captured["html"]


def test_public_cover_level_omits_full_only_blocks(client, db_session):
    est, link = _estimate_with_link(db_session, token="tok-cover", level="cover")
    est.proposal = {"title": "Заголовок КП", "pain": "Боль клиента", "cta": "Звоните"}
    db_session.commit()
    body = client.get(f"/p/{link.token}").text
    assert "Заголовок КП" in body  # титул — на уровне cover есть
    assert "Боль клиента" not in body  # pain — только на уровне full
