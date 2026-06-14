"""Фоновый воркер: один поток в процессе бэкенда выполняет задачи из таблицы jobs.

Подходит для одно-инстансного деплоя (один uvicorn-процесс). При горизонтальном
масштабировании нужен распределённый лок (Redis / SELECT FOR UPDATE)."""
import os
import threading

from sqlalchemy import select, update

from app.catalog import characteristics as ch
from app.core.db import SessionLocal
from app.jobs.models import Job

_stop = threading.Event()
_thread: threading.Thread | None = None
_MAX_BATCHES = 1000


def _run_catalog_extract(db, job: Job) -> None:
    supplier_id = (job.params or {}).get("supplier_id")
    total = ch._remaining(db, supplier_id)
    job.total = total
    job.processed = 0
    job.message = f"обработано 0/{total}"
    db.commit()
    for _ in range(_MAX_BATCHES):
        r = ch.extract_batch(db, batch=15, supplier_id=supplier_id)
        if r["processed"] == 0:
            break
        job.processed = total - r["remaining"] if total else job.processed + r["processed"]
        job.message = f"обработано {job.processed}/{total}"
        db.commit()
        if r["remaining"] <= 0:
            break


HANDLERS = {"catalog_extract": _run_catalog_extract}


def claim_and_run(db) -> bool:
    """Берёт старейшую pending-задачу и выполняет. True, если что-то выполнил."""
    job = db.scalars(
        select(Job).where(Job.status == "pending").order_by(Job.id).limit(1)
    ).first()
    if job is None:
        return False
    job.status = "running"
    db.commit()
    handler = HANDLERS.get(job.type)
    try:
        if handler is None:
            raise ValueError(f"Неизвестный тип задачи: {job.type}")
        handler(db, job)
        job.status = "done"
        job.error = ""
    except Exception as exc:  # noqa: BLE001 — ошибку задачи фиксируем в самой задаче
        db.rollback()
        job = db.get(Job, job.id)
        if job is not None:
            job.status = "error"
            job.error = str(exc)[:1000]
    db.commit()
    return True


def _loop() -> None:
    while not _stop.is_set():
        did = False
        try:
            with SessionLocal() as db:
                did = claim_and_run(db)
        except Exception:  # noqa: BLE001 — воркер не должен падать
            did = False
        _stop.wait(0.05 if did else 0.5)


def recover_orphaned(db) -> int:
    """Сбросить задачи, застрявшие в 'running' (процесс упал) → 'error'.
    Безопасно при одном инстансе: на старте никакой воркер их легитимно не держит."""
    res = db.execute(
        update(Job).where(Job.status == "running")
        .values(status="error", error="прервано перезапуском сервера")
    )
    db.commit()
    return res.rowcount


def start_worker() -> None:
    global _thread
    if os.getenv("JOBS_WORKER_DISABLED"):  # в тестах воркер-поток не нужен
        return
    if _thread and _thread.is_alive():
        return
    with SessionLocal() as db:
        recover_orphaned(db)
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="jobs-worker", daemon=True)
    _thread.start()


def stop_worker() -> None:
    _stop.set()
    if _thread:
        _thread.join(timeout=5)
