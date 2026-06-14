import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Воркер-поток не запускаем в тестах (он бы лез в реальную БД через SessionLocal).
# Должно стоять до создания TestClient (триггерит lifespan→start_worker).
os.environ.setdefault("JOBS_WORKER_DISABLED", "1")

from app.auth import models as _models  # noqa: E402, F401 — регистрирует таблицы в metadata
from app.catalog import models as _catalog_models  # noqa: E402, F401
from app.core.db import Base, get_db  # noqa: E402
from app.estimates import models as _estimate_models  # noqa: E402, F401
from app.profile import models as _profile_models  # noqa: E402, F401
from app.publiclinks import models as _publiclink_models  # noqa: E402, F401
from app.ai import models as _ai_models  # noqa: E402, F401
from app.jobs import models as _jobs_models  # noqa: E402, F401
from app.main import app  # noqa: E402


@pytest.fixture()
def db_session():
    from sqlalchemy import event

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _register_lower(dbapi_conn, _):
        dbapi_conn.create_function("lower", 1, lambda s: s.lower() if isinstance(s, str) else s)

    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    with TestingSession() as session:
        yield session


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def client_app(client):
    return client
