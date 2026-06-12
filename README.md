# SmetaApp

Приложение для составления смет и КП на базе прайсов поставщиков.
Дизайн системы: `docs/superpowers/specs/2026-06-11-smeta-app-design.md`.

## Стек

FastAPI + PostgreSQL + React (Vite, Tailwind) + Caddy. Подробности — в спеке.

## Разработка

```powershell
docker compose -f docker-compose.dev.yml up -d --build
# фронт: http://localhost:5173, API: http://localhost:8000/docs
```

Dev-Postgres слушает хост-порт 5433 (5432 на машине разработчика занят).

Тесты: `cd backend; .venv\Scripts\python -m pytest -q` и `cd frontend; npm run test`.

## Прод

Скопировать `.env.example` → `.env`, заполнить секреты, затем:

```bash
docker compose up -d --build
```

## Яндекс OAuth

Создать приложение на https://oauth.yandex.ru/ (доступ: email, имя),
redirect URI: `<BACKEND_URL>/api/auth/yandex/callback`.
ID/секрет — в `.env` (`YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`).
Первый зарегистрировавшийся пользователь автоматически становится активным админом.
