from sqlalchemy import select

from app.ai import service as ai_service
from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.core.security import create_access_token
from app.jobs import worker
from app.jobs.models import Job
from app.orgs.models import Organization


def _get_or_create_org(db):
    org = db.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db.add(org)
        db.commit()
    return org


def _admin(db):
    org = _get_or_create_org(db)
    u = User(email="a@x.ru", name="A", role="org_admin", status="active", org_id=org.id)
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _item(db, name="Камера 2Мп"):
    org = _get_or_create_org(db)
    sup = Supplier(name="P", org_id=org.id); db.add(sup); db.commit()
    it = CatalogItem(
        supplier_id=sup.id, name=name, article="A", unit="шт", kind="material", org_id=org.id
    )
    db.add(it); db.commit(); db.refresh(it)
    return it


def test_claim_and_run_executes_catalog_extract(db_session, monkeypatch):
    it = _item(db_session)
    org = _get_or_create_org(db_session)
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {
        "items": [{"id": it.id, "characteristics": {"Разрешение": "2 Мп"}}]})
    job = Job(type="catalog_extract", params={"org_id": org.id})
    db_session.add(job); db_session.commit()

    assert worker.claim_and_run(db_session) is True
    db_session.refresh(job); db_session.refresh(it)
    assert job.status == "done"
    assert job.total == 1 and job.processed == 1
    assert it.characteristics == {"Разрешение": "2 Мп"}


def test_claim_and_run_unknown_type_sets_error(db_session):
    job = Job(type="nonsense", params={})
    db_session.add(job); db_session.commit()
    assert worker.claim_and_run(db_session) is True
    db_session.refresh(job)
    assert job.status == "error"
    assert "Неизвестный" in job.error


def test_claim_and_run_returns_false_when_empty(db_session):
    assert worker.claim_and_run(db_session) is False


def test_start_endpoint_enqueues_and_dedups(client, db_session):
    a = _admin(db_session)
    _item(db_session)
    r1 = client.post("/api/catalog/extract-characteristics/start", headers=_hdr(a))
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["type"] == "catalog_extract" and body["status"] == "pending"
    # повторный запуск при активной задаче → та же задача
    r2 = client.post("/api/catalog/extract-characteristics/start", headers=_hdr(a))
    assert r2.json()["id"] == body["id"]


def test_start_endpoint_admin_only(client, db_session):
    org = _get_or_create_org(db_session)
    e = User(email="e@x.ru", name="E", role="estimator", status="active", org_id=org.id)
    db_session.add(e); db_session.commit()
    r = client.post("/api/catalog/extract-characteristics/start", headers=_hdr(e))
    assert r.status_code == 403


def test_recover_orphaned_running_jobs(db_session):
    db_session.add(Job(type="catalog_extract", status="running", params={}))
    db_session.add(Job(type="catalog_extract", status="pending", params={}))
    db_session.commit()
    n = worker.recover_orphaned(db_session)
    assert n == 1
    statuses = sorted(j.status for j in db_session.scalars(select(Job)).all())
    assert statuses == ["error", "pending"]


def test_get_job_status(client, db_session):
    a = _admin(db_session)
    job = Job(type="catalog_extract", status="running", processed=3, total=10,
              message="обработано 3/10", params={})
    db_session.add(job); db_session.commit()
    r = client.get(f"/api/jobs/{job.id}", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json()["processed"] == 3 and r.json()["total"] == 10
    assert client.get("/api/jobs/99999", headers=_hdr(a)).status_code == 404
