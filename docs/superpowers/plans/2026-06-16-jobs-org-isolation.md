# Изоляция фоновых задач по организации — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Закрыть межорг-утечку `GET /api/jobs/{id}`: добавить `org_id` колонкой в `jobs`, проставлять при создании, фильтровать в GET (чужое → 404).

**Architecture:** Новая NOT NULL колонка `Job.org_id` (FK organizations, индекс), backfill из `params->>'org_id'`. `start_extract_characteristics` ставит `org_id`. `get_job` скоупит по `current_org`.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + pytest (SQLite). Текущий head миграций: `c4d5e6f7a8b9`.

**Спек:** `docs/superpowers/specs/2026-06-16-jobs-org-isolation-design.md`

**Команды (из `backend`):** тесты `./.venv/Scripts/python.exe -m pytest -q`; одиночный `... -m pytest tests/test_jobs.py -q`; линт `./.venv/Scripts/ruff.exe check .` (ВЕСЬ репо — CI гонит так; `alembic/versions/*` игнорит только E501, не I001 → импорты в миграции сортировать).

---

## Структура файлов
- Изменить: `backend/app/jobs/models.py` (Job +org_id), `backend/app/jobs/router.py` (get_job скоуп), `backend/app/catalog/router.py` (start_extract_characteristics ставит org_id).
- Создать: `backend/alembic/versions/f7a8b9c0d1e2_jobs_org.py`.
- Тест: `backend/tests/test_jobs.py` (новый кейс + правка фикстур).

---

## Task 1: org_id на jobs + изоляция GET

**Files:** Modify `backend/app/jobs/models.py`, `backend/app/jobs/router.py`, `backend/app/catalog/router.py`. Create `backend/alembic/versions/f7a8b9c0d1e2_jobs_org.py`. Test `backend/tests/test_jobs.py`.

- [ ] **Step 1: Failing test** — добавить в `backend/tests/test_jobs.py` (вверху файла дополнить импорты `Organization`, `create_access_token`, если их нет):

```python
from app.auth.models import User
from app.core.security import create_access_token
from app.jobs.models import Job
from app.orgs.models import Organization


def _org_admin(db, name):
    o = Organization(name=name); db.add(o); db.commit()
    u = User(email=f"j{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u); db.commit(); return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_job_not_visible_across_orgs(client, db_session):
    oa, ua = _org_admin(db_session, "JA"); ob, ub = _org_admin(db_session, "JB")
    job = Job(type="catalog_extract", status="done", org_id=oa.id,
              params={"supplier_id": None, "org_id": oa.id})
    db_session.add(job); db_session.commit()
    assert client.get(f"/api/jobs/{job.id}", headers=_hdr(ub)).status_code == 404
    assert client.get(f"/api/jobs/{job.id}", headers=_hdr(ua)).status_code == 200
```

- [ ] **Step 2: Run → FAIL** `./.venv/Scripts/python.exe -m pytest tests/test_jobs.py::test_job_not_visible_across_orgs -q` → ошибка: `Job` не имеет `org_id` (TypeError) либо 200 вместо 404.

- [ ] **Step 3: Модель.** В `backend/app/jobs/models.py` добавить `ForeignKey` в импорт sqlalchemy (`from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func`) и в класс `Job` (после `id`):

```python
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
```

- [ ] **Step 4: Создание задачи ставит org_id.** В `backend/app/catalog/router.py` `start_extract_characteristics` (строка ~426) заменить:

```python
    job = Job(type="catalog_extract", params={"supplier_id": supplier_id, "org_id": org})
```
на:
```python
    job = Job(type="catalog_extract", org_id=org,
              params={"supplier_id": supplier_id, "org_id": org})
```

- [ ] **Step 5: GET скоупит по орг.** В `backend/app/jobs/router.py` добавить импорт `current_org` (`from app.auth.deps import current_org, require_active`) и переписать `get_job`:

```python
@router.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    org: int = Depends(current_org),
):
    job = db.get(Job, job_id)
    if job is None or job.org_id != org:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return job
```

- [ ] **Step 6: Миграция** `backend/alembic/versions/f7a8b9c0d1e2_jobs_org.py` (импорты отсортированы: `from collections.abc import Sequence` ПОСЛЕ пустой строки идут `import sqlalchemy as sa` / `from alembic import op` — иначе ruff I001 в CI):

```python
"""jobs.org_id (FK + NOT NULL, backfill from params)

Revision ID: f7a8b9c0d1e2
Revises: c4d5e6f7a8b9
Create Date: 2026-06-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("org_id", sa.Integer(), nullable=True))
    # backfill: org_id из params (JSONB на Postgres), остаток → дефолтная орг
    op.execute("UPDATE jobs SET org_id = (params->>'org_id')::int WHERE params ? 'org_id'")
    op.execute("UPDATE jobs SET org_id = (SELECT min(id) FROM organizations) WHERE org_id IS NULL")
    op.alter_column("jobs", "org_id", nullable=False)
    op.create_foreign_key("fk_jobs_org", "jobs", "organizations", ["org_id"], ["id"])
    op.create_index("ix_jobs_org_id", "jobs", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_org_id", table_name="jobs")
    op.drop_constraint("fk_jobs_org", "jobs", type_="foreignkey")
    op.drop_column("jobs", "org_id")
```

- [ ] **Step 7: Поправить существующие тесты jobs.** В `backend/tests/test_jobs.py` к КАЖДОМУ прямому созданию `Job(...)` добавить `org_id=<org>.id` (Job теперь NOT NULL по org_id). Где тест дергает `/api/jobs/{id}` под юзером — у юзера должен быть `org_id`, совпадающий с org_id задачи. Если в тест-хелперах юзер без орг — завести орг (через `from tests.orghelpers import get_or_create_org`) и проставить и юзеру, и задаче один и тот же `org_id`. Прогнать `./.venv/Scripts/python.exe -m pytest tests/test_jobs.py -q` до зелёного.

- [ ] **Step 8: Полный прогон + линт.** `./.venv/Scripts/python.exe -m pytest -q` → всё зелёное (1 skipped weasyprint ок). `./.venv/Scripts/ruff.exe check .` → чисто.

- [ ] **Step 9: Commit**
```bash
git add backend/app/jobs backend/app/catalog/router.py backend/alembic/versions/f7a8b9c0d1e2_jobs_org.py backend/tests/test_jobs.py
git commit -m "fix(jobs): org_id колонка + изоляция GET /api/jobs/{id} (закрыта межорг-утечка I-2)"
```
(в теле коммита — трейлер `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`)

---

## Финальная проверка
- [ ] `pytest -q` + `ruff check .` зелёные.
- [ ] `alembic heads` → один head `f7a8b9c0d1e2`; цепочка `c4d5e6f7a8b9 → f7a8b9c0d1e2`.
- [ ] Спек-ревью + ревью качества (субагентно).
