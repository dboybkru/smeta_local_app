# Реквизиты клиентов + интеграция DaData: дизайн

> Брейншторм-дизайн, 2026-06-14. Закрывает недоделку «нет реквизитов клиентов». Полный набор реквизитов (юр+физ) + автозаполнение по ИНН/названию через DaData. Реквизиты идут в КП/экспорт.

## Решения (зафиксировано)

1. **Реквизиты:** полный набор — `inn, kpp, ogrn, type` (LEGAL/INDIVIDUAL), `address` (юр), `actual_address` (факт), `phone, email, contact_person, bank_name, bank_account, bik`.
2. **DaData:** автодополнение по названию/ИНН → автозаполнение реквизитов. Ключ DaData — **в админке (шифр в БД)**, как AI-ключи.
3. **UI:** отдельная страница **«Клиенты»** (`/clients`): список + создание/редактирование с DaData-автозаполнением. Быстрый выбор клиента в смете остаётся.
4. **DaData не отдаёт** телефон/email/банк → их вписывают вручную. Заполняет: название, ИНН, КПП, ОГРН, адрес, руководитель, тип.

## DaData API (проанализировано)

- `POST https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party` — `{query, count≤20}` → `suggestions[].data.{inn,kpp,ogrn,name.short_with_opf,address.value,management.name,type,state.status}`.
- Авторизация: `Authorization: Token <API_KEY>` (только ключ, без secret).
- Бесплатно 10k/день, 30 req/s.

## Бэкенд

### Настройки приложения (для ключа DaData) — модуль `app/settings/`
- Таблица `app_settings(key: str PK, value: Text)`; значения-секреты шифруются Fernet (переиспользуем `app.ai.crypto`).
- `service.get_secret(db, key) -> str` (decrypt, "" если нет), `set_secret(db, key, value)`, `has_secret(db, key) -> bool`.
- Эндпоинты (`require_admin`): `GET /api/settings/dadata` → `{has_token: bool}`; `PUT /api/settings/dadata` body `{token: str}` (write-only; пустой = не менять). Ключ `dadata_token`.
- Миграция: таблица `app_settings`.

### DaData-клиент + прокси
- `app/clients/dadata.py`: `suggest_parties(token, query, count=10, *, http=None) -> list[dict]` — POST к suggest/party, маппит в `[{value, inn, kpp, ogrn, name_short, address, management, type, status}]`; ошибки сети → `[]` (best-effort, не валим UI). http DI для тестов.
- Эндпоинт `GET /api/clients/suggest?q=` (`require_active`) → если токен не задан → `[]`; иначе `suggest_parties(token, q)`. Возвращает упрощённые подсказки.

### Модель Client + CRUD
- Расширить `Client` (новые поля nullable str): `inn, kpp, ogrn, type, address, actual_address, phone, email, contact_person, bank_name, bank_account, bik`. Миграция (add columns).
- `ClientIn`/`ClientOut`/`ClientPatch` — все поля. `GET /api/clients` (есть), `POST /api/clients` (расширить), **`PATCH /api/clients/{id}`** (новый), `GET /api/clients/{id}` (новый). `require_active`.

### Экспорт — блок «Заказчик»
- `build_export_context` добавляет `client` (dict реквизитов клиента сметы; в public-режиме — без банковских деталей? нет, КП заказчику — реквизиты заказчика показывать можно; банк исполнителя в профиле). Включаем имя/ИНН/КПП/адрес/контакт.
- HTML-шаблон `proposal.html` + `excel.py`: блок «Заказчик: …» под объектом.

## Фронтенд

| Файл | Изменение |
|---|---|
| `api/clients.ts` (новый) | типы Client(+реквизиты), `listClients`, `getClient`, `createClient`, `updateClient`, `suggestParties(q)` |
| `api/ai.ts` или новый `api/settings.ts` | `getDadataSettings()`/`setDadataToken(token)` |
| `pages/ClientsPage.tsx` (новый) | список клиентов + форма создания/редактирования; поле поиска с DaData-выпадашкой → автозаполнение |
| `components/ai/...` или AiConfigPage | секция «Интеграции / DaData»: поле ключа (password, «ключ задан») |
| `App.tsx` / `AppHeader.tsx` | маршрут `/clients` + ссылка «Клиенты» (canEdit) |
| `EstimateHeader.tsx` | существующий выбор клиента остаётся; ссылка «управление клиентами» опц. |

- **ClientsPage:** таблица клиентов (имя, ИНН, телефон). Кнопка «Добавить» / клик по строке → форма. В форме сверху — поиск «Найти по названию/ИНН» (debounce → `suggestParties`) → выпадашка → выбор автозаполняет name/inn/kpp/ogrn/address/contact_person(=management.name)/type; остальное (тел/email/банк/факт.адрес) — вручную. Сохранить → create/update.
- **DaData-настройка:** в `/admin/ai` (или ClientsPage) секция с password-полем ключа DaData (как ключ провайдера: write-only, показываем «ключ задан/нет»).

## Ошибки / безопасность

- Токен DaData — только на сервере (прокси), в браузер не уходит; шифр в БД.
- Нет токена → `/clients/suggest` отдаёт `[]`, ручной ввод работает (фича не ломается).
- DaData недоступна/ошибка → `[]` (best-effort).
- DaData-вызовы — `require_active` (любой залогиненный редактор); ключ-настройка — `require_admin`.

## Тестирование (pytest + Vitest, мок DaData http / fetch)

- **Backend:** settings.get/set_secret (шифр round-trip); `GET/PUT /settings/dadata` (admin, has_token); `dadata.suggest_parties` (мок httpx.MockTransport → маппинг полей; сеть-ошибка → []); `GET /clients/suggest` (нет токена → []; с токеном+мок → подсказки); Client PATCH/GET + новые поля в ClientOut; export-контекст содержит client-блок.
- **Frontend:** ClientsPage (список; форма; DaData-поиск мок fetch → выбор автозаполняет поля; сохранение PATCH/POST); DaData-настройка (PUT токена); AppHeader ссылка «Клиенты».
- Сборка/линт/ruff чисто. Миграции (`app_settings` + client columns) на боевом Postgres при деплое (nullable/JSON безопасно, boolean не задействован).

## Отложено

- DaData Clean API (стандартизация адресов), банковские подсказки по БИК (DaData умеет suggest/bank — позже).
- Дедуп клиентов по ИНН (можно добавить уник-ограничение позже).
- Реквизиты клиента в Excel-экспорт деталях банка.
