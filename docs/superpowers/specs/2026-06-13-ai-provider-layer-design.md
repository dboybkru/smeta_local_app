# Слой AI-провайдеров (VseGPT / AITunnel) — дизайн

> Брейншторм-дизайн, 2026-06-13. Заменяет прямой вызов Anthropic в фазе 4a на конфигурируемый из админки слой «провайдер + модель на цель» с моделью-роутером (советником).

## Зачем

Генерация текстов КП (фаза 4a) сейчас жёстко зовёт Anthropic SDK (`_call_claude`). Нужно: подключить рублёвые OpenAI-совместимые агрегаторы **VseGPT** и **AITunnel**, выбирать **провайдера+модель под каждую цель** из админки, по соотношению цена-качество, и иметь «главную модель», которая анализирует доступные модели и цели и **советует** оптимальный выбор.

## Подтверждённые провайдеры (по их докам)

| Провайдер | base_url | Авторизация | Формат |
|---|---|---|---|
| AITunnel | `https://api.aitunnel.ru/v1/` | `Authorization: Bearer sk-aitunnel-…` | OpenAI Chat Completions (`/v1/chat/completions`); есть `model:"auto"` |
| VseGPT | `https://api.vsegpt.ru/v1` | `X-Api-Key: sk-or-v…` (OpenRouter-стиль) | OpenAI Chat Completions |

Оба — OpenAI-совместимы. Чистого API «список моделей с ценами» нет (только id через `GET /v1/models`; цены — на веб-страницах). → каталог моделей с ценами ведём в админке.

## Зафиксированные решения

1. **Цели — расширяемый список (данные, не enum).** Строки в таблице; новые добавляются без миграций. Сид: `proposal_generation`, `estimate_analysis`, `assistant`, `router`. Список заведомо неполный — это норма.
2. **Роутер — советник на этапе настройки** (не рантайм). В админке «подобрать модели» → роутер-модель читает каталог + цели → предлагает провайдер+модель на цель; админ принимает/правит. Рантайм идёт по зафиксированному выбору (дёшево, без точки отказа на каждый запрос).
3. **Ключи — в БД, шифрованные (Fernet от `SECRET_KEY`), через админку.** Один ключ на провайдера, общий для приложения. Поле write-only (вводишь — обратно не отдаётся).
4. **Каталог моделей — админка + автоимпорт id** (`GET /v1/models`), цены/заметки проставляются вручную у нужных моделей.
5. **Фолбэк — основная + опц. запасная модель на каждую цель** (запасная может быть на другом провайдере). Ошибка основной → пробуем запасную → иначе 502.
6. **Клиент — `httpx`** (уже в зависимостях) к `/v1/chat/completions`, заголовок авторизации по `auth_style` провайдера. Генерация уходит с Anthropic SDK; `anthropic` убирается из requirements.
7. **Охват спека — бэкенд-слой + конфиг-API.** Админ-UI — в отдельную фронтенд-фазу.

## Архитектура

Поток: `proposals/service` (и будущие фичи) → `ai.service.call_llm(db, purpose_key, messages, json_schema?)` → резолв цели → основная модель+провайдер → `ai.client` (httpx → `/v1/chat/completions`) → при ошибке → запасная модель → иначе `AIError(502)`. Нет модели / провайдер выключен → `AINotConfigured(503)`.

Модуль `backend/app/ai/` (уже есть пустой `__init__.py`).

## Модель данных (3 таблицы; миграция вручную, проверка на Postgres; boolean `server_default=false`)

- **`AIProvider`** — `id, name (unique), base_url, auth_style ('bearer'|'x_api_key'), api_key_encrypted (text, Fernet, write-only), enabled (bool), created_at, updated_at`.
- **`AIModel`** (каталог) — `id, provider_id→AIProvider, model_id (str, напр. "anthropic/claude-3.5-sonnet"), label, input_price/output_price (Numeric, nullable, ₽/1M ток.), strengths (text, для роутера), enabled (bool)`. `unique(provider_id, model_id)`.
- **`AIPurpose`** (цели, data-driven) — `id, key (unique slug), title, description (контекст для роутера), primary_model_id→AIModel (nullable), fallback_model_id→AIModel (nullable), enabled (bool)`. Сид четырьмя целями; роутер — цель `key="router"`.

Регистрация моделей в `tests/conftest.py`. Миграция сидит 4 цели.

## Компоненты

### `ai/crypto.py`
`encrypt(plain)->str` / `decrypt(token)->str` через Fernet; ключ выводится из `settings.secret_key` (стабильно между рестартами). Зависимость `cryptography`.

### `ai/client.py`
`chat_completion(provider, model_id, messages, *, max_tokens, json_mode) -> str`:
- httpx `POST {provider.base_url}/chat/completions`, заголовок по `auth_style`, тело `{model: model_id, messages, max_tokens, response_format:{"type":"json_object"} если json_mode}`.
- Возвращает `choices[0].message.content`. Таймаут (60 c). HTTP/сетевые ошибки → `AIError`. Ключ расшифровывается здесь.
- `list_models(provider) -> list[str]` — `GET {base_url}/models` → id для автоимпорта.

### `ai/service.py`
- Исключения `AINotConfigured` (→503), `AIError` (→502).
- `call_llm(db, purpose_key, messages, *, json_schema=None, max_tokens=2000) -> dict|str`:
  - Резолв `AIPurpose[key]` (enabled) → primary модель+провайдер (enabled). Нет/выключено → `AINotConfigured`.
  - `json_mode = json_schema is not None`. Для JSON: `response_format=json_object` + схема добавляется в системный промпт (json_object даёт валидный JSON, но не гарантирует схему) → парсим → возвращаем dict; вызывающий валидирует своей Pydantic-моделью. Без схемы — строка.
  - Фолбэк: primary упала (`AIError`) → пробуем `fallback_model` (если задан) → обе упали → `AIError`.

### `ai/router_advisor.py`
`recommend_models(db) -> list[{purpose_key, provider, model_id, rationale}]`:
- Собирает каталог enabled-моделей (провайдер, цены, strengths) + цели (key/title/description).
- Промпт: «вот модели с ценами/сильными сторонами, вот цели — подбери под каждую лучшую по цена-качество, дай однострочное обоснование, верни JSON».
- Зовёт `call_llm(db, "router", …, json_schema=RECOMMENDATION_SCHEMA)`. **Только предлагает**, применяет админ.

## API (всё под `require_admin`, префикс `/api/ai`)

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/providers` | список (без ключей; `has_key: bool`) |
| POST | `/providers` | создать (ключ пишется, шифруется) |
| PUT | `/providers/{id}` | обновить (ключ опционален: пусто = не менять) |
| DELETE | `/providers/{id}` | удалить |
| POST | `/providers/{id}/models/refresh` | импорт id моделей через `GET /v1/models` |
| GET | `/models?provider_id=` | список каталога |
| PUT | `/models/{id}` | цены/strengths/enabled |
| DELETE | `/models/{id}` | удалить из каталога |
| GET | `/purposes` | список целей с текущими primary/fallback |
| PUT | `/purposes/{key}` | задать primary/fallback модель, description, enabled |
| POST | `/router/recommend` | предложения роутера (не применяет) |
| POST | `/purposes/{key}/test` | крошечный `call_llm` для проверки цели → ok/ошибка |

## Перенос генерации КП

`proposals/service.generate_proposal(db, estimate, profile)` — принимает `db`; вместо `_call_claude` зовёт `call_llm(db, "proposal_generation", messages, json_schema=PROPOSAL_SCHEMA)`; валидация `ProposalBlocks` остаётся. В роутере КП: `ai.AINotConfigured`→503, `ai.AIError`→502 (заменяет `ProposalAINotConfigured`/`ProposalAIError`). `_call_claude`, `_OUTPUT_SCHEMA` Anthropic-вызов и импорт `anthropic` удаляются; `anthropic` — из requirements.

## Безопасность

- Ключи провайдеров — только Fernet-шифр в БД; в ответах API не отдаются (`has_key`); не логируются.
- Вся конфигурация AI — только `require_admin`.
- `PUT /providers/{id}` без поля `api_key` сохраняет существующий ключ (write-only семантика).

## Тестирование (весь HTTP замокан, без реальной сети)

- `crypto`: encrypt→decrypt round-trip.
- `client.chat_completion`: строит верный запрос по `auth_style` (мок httpx — проверка заголовка `Authorization`/`X-Api-Key` и тела), парсит `content`; ошибка → `AIError`.
- `call_llm`: резолв цель→модель→провайдер; json-режим парсит dict; **фолбэк** при ошибке primary → пробует fallback; `AINotConfigured` когда цель/модель не настроена или провайдер выключен.
- `router_advisor.recommend_models`: `call_llm` замокан → возвращает предложения.
- Admin-API: provider CRUD с write-only ключом (GET никогда не отдаёт ключ); `models/refresh` (мок `GET /v1/models`); purpose PUT задаёт primary/fallback.
- Перенос КП: `generate_proposal` через мокнутый `call_llm` пишет блоки; 503 без конфигурации; 502 при `AIError`.

## Файлы

- `backend/app/ai/{models,schemas,crypto,client,service,router_advisor,router}.py`
- миграция `…_ai_provider_layer.py` (3 таблицы + сид 4 целей; boolean `server_default=false`)
- `backend/tests/conftest.py` — регистрация моделей `app.ai.models`
- `backend/app/proposals/{service,router}.py` — перенос на `call_llm`
- `backend/requirements.txt` — `+cryptography`, `−anthropic`
- тесты: `test_ai_crypto.py`, `test_ai_client.py`, `test_ai_service.py`, `test_ai_router_advisor.py`, `test_ai_admin_api.py`, правка `test_proposal_*`

## Отложено (не в этом спеке)

- Админ-UI (фронтенд-фаза): управление провайдерами/моделями/целями, кнопка «подобрать модели» (роутер), индикатор баланса.
- Рантайм-роутинг и `model:"auto"` AITunnel (можно добавить как опцию на цель позже).
- Интерактивный AI-ассистент редактора (фаза 5) — будет потреблять `call_llm(purpose="assistant")`.
- Per-user ключи/баланс.
