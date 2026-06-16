# Изоляция фоновых задач по организации (jobs.org_id) — дизайн

**Дата:** 2026-06-16
**Статус:** на ревью пользователя (брейншторм)
**Очередь:** A (этот спек) → B (httpOnly-cookie+CSRF) → C (email-инвайты)

## Проблема

`GET /api/jobs/{job_id}` (`backend/app/jobs/router.py:13-22`) достаёт `Job` по id и гейтится только `require_active` — **без проверки организации**. Модель `Job` (`app/jobs/models.py`) не имеет колонки `org_id`; орг-контекст лежит только в `Job.params` (JSON, ключ `org_id`, кладётся воркером с Этапа A). Любой аутентифицированный пользователь может перебором id читать прогресс/`message` чужой задачи (метаданные другой орг). Это последняя межорг-щель Этапа A (находка I-2 финального ревью).

## Решение (принято на брейншторме)

Сделать `org_id` **колонкой первого класса** в `jobs` (как у всех остальных орг-таблиц Этапа A), а не полагаться на JSON. Фильтровать GET по ней.

## Изменения

### Модель
`app/jobs/models.py` — добавить:
```python
org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
```
(NOT NULL обеспечивает миграция; атрибут без `| None`.)

### Миграция
Новая, `down_revision = "c4d5e6f7a8b9"` (текущий head):
1. `add_column` `org_id` nullable.
2. Backfill: `UPDATE jobs SET org_id = (params->>'org_id')::int WHERE params ? 'org_id'` (Postgres JSON). Остаток (legacy без org_id в params) → дефолтная орг: `UPDATE jobs SET org_id = (SELECT min(id) FROM organizations) WHERE org_id IS NULL`.
3. `alter_column` NOT NULL + FK + index.
Boolean-правил тут нет; учесть кросс-БД: тесты создают схему через `create_all` из модели, миграция-backfill пишется под Postgres (прод).

### Создание задачи
`app/catalog/router.py` `start_extract_characteristics` — ставить `org_id=org` (из `current_org`) на создаваемый `Job`. `params["org_id"]` оставляем (воркер `app/jobs/worker.py` читает его) — колонка становится границей доступа, params — рабочий параметр.

### Эндпоинт
`app/jobs/router.py` `get_job` — добавить `org: int = Depends(current_org)`; после `db.get(Job, job_id)`: если `job is None or job.org_id != org` → 404 (одинаковый ответ, не раскрываем существование).

## Тестирование
- `tests/test_jobs.py`: орг B запрашивает id задачи орг A → 404; своя задача → 200; создание задачи проставляет `org_id`.
- Существующие тесты jobs: добавить `org_id` в фикстуры создания `Job`.
- Полный прогон зелёный, `ruff check .` (весь backend, не только app/) чист.

## Вне рамок
Листинг задач по орг (эндпоинта-списка нет — только GET по id). Распределённый claim воркера (отдельный долг, single-instance).
