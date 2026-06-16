# httpOnly-cookie аутентификация + CSRF — дизайн

**Дата:** 2026-06-16
**Статус:** на ревью пользователя (брейншторм)
**Очередь:** A (jobs) → B (этот спек) → C (email-инвайты)

## Проблема

Фронтенд хранит access/refresh JWT в `localStorage` (`frontend/src/api/client.ts:5-18`, есть собственный `TODO(security)`). localStorage доступен любому XSS → токены воруются. Яндекс-callback (`app/auth/router.py:120-123`) отдаёт токены в **URL-fragment** (утечка в историю/реферер/логи).

## Решение (принято на брейншторме)

Перевести сессию на **httpOnly-cookie** (JS не видит токены) + **double-submit CSRF-токен**. SameSite=**Lax** (не Strict: Strict ломает возврат Яндекс-OAuth и UX перехода по внешним ссылкам; в коде `yx_state` уже Lax). Backend читает access из cookie **ИЛИ** из заголовка `Authorization: Bearer` (cookie-first) — чтобы 350+ существующих тестов и API-клиенты работали без правок.

## Схема cookie (все `Secure`, `SameSite=Lax`)
| Cookie | httpOnly | path | max_age |
|---|---|---|---|
| `access_token` | да | `/api` | TTL access |
| `refresh_token` | да | `/api/auth` (шлётся только на auth) | 30 дней |
| `csrf_token` | **нет** (JS читает) | `/` | сессия |

`Secure` конфигурируем: `settings.cookie_secure` (env `COOKIE_SECURE`, дефолт `true`; локальный dev на http ставит `false`, иначе браузер не примет cookie).

## Backend

### Чтение токена
`app/auth/deps.py` `get_current_user`: сначала `request.cookies.get("access_token")`, при отсутствии — заголовок `Authorization: Bearer` (текущий HTTPBearer). Декод как сейчас. Это сохраняет тест-клиент (Bearer) и API-клиентов.

### CSRF-middleware (`app/main.py`)
Один middleware: для небезопасных методов (POST/PUT/PATCH/DELETE) к `/api/*`, **только если запрос аутентифицирован cookie** (присутствует cookie `access_token`), требовать заголовок `X-CSRF-Token` == cookie `csrf_token`, иначе 403. Запросы с `Authorization: Bearer` (тесты/API) CSRF НЕ проверяются — они by design иммунны к CSRF (атакующий не выставит заголовок кросс-сайт). → существующие Bearer-тесты не ломаются. Исключения (сессию устанавливают / GET): `/api/auth/login`, `/api/auth/register`, `/api/auth/refresh`, `/api/auth/yandex/*`, `/api/auth/invite/*` (из C). Их защищает SameSite + OAuth-state + одноразовый токен инвайта.

### Эндпоинты auth
- `login`: authenticate → ставит access+refresh+csrf cookie → возвращает `UserOut` (SPA сразу знает identity, без лишнего `/me`). 200.
- `register`: ставит cookie ТОЛЬКО если итоговый юзер `active` (бутстрап первого юзера); `pending` — без cookie (нет доступа). Возвращает `UserOut`. (В C открытый register становится bootstrap-only.)
- `refresh`: читает refresh из cookie (фолбэк — body `RefreshIn` для тестов/клиентов) → ставит новые access+csrf cookie (refresh-cookie перевыпускаем) → возвращает `UserOut`.
- **`logout` (новый)** `POST /api/auth/logout`: чистит access/refresh/csrf cookie → 204.
- `yandex/callback`: вместо токенов в URL-fragment — ставит cookie на `RedirectResponse` и редиректит на чистый `{frontend_url}/auth/callback` (без fragment). Страница callback зовёт `/me`.

### Хелпер
`app/auth/cookies.py` (новый): `set_auth_cookies(response, access, refresh, csrf)` и `clear_auth_cookies(response)` — единое место флагов/путей/max_age, чтобы не дублировать в 5 эндпоинтах.

## Frontend (`api/client.ts`)
- Убрать `getTokens/setTokens/clearTokens` и Bearer-логику. Все запросы — `credentials: "same-origin"` (cookie шлётся сам; API на том же домене через nginx).
- Хелпер `getCsrf()` читает cookie `csrf_token` из `document.cookie`; на небезопасных методах добавлять `X-CSRF-Token`.
- Refresh-on-401: сохранить общий in-flight промис, но без работы с токенами — на 401 POST `/auth/refresh` (cookie сам) → ретрай один раз.
- `AuthContext`/выход: logout зовёт `POST /api/auth/logout`; состояние логина определяется по `/me` (401 = не залогинен) — как сейчас.
- `AuthCallbackPage`: больше не парсит fragment — просто зовёт `/me` и роутит (cookie уже стоят от callback).

## Тестирование
- Backend (новые): login/refresh/logout ставят/чистят cookie с httpOnly; `/me` через cookie; CSRF-middleware блокит cookie-мутацию без/с неверным `X-CSRF-Token` (403) и пускает с верным; Bearer-мутация без CSRF проходит (иммунитет); yandex-callback ставит cookie + редирект без fragment. Существующие Bearer-тесты — без изменений.
- Frontend (новые): `client.ts` шлёт `X-CSRF-Token` на мутациях; refresh-on-401 без localStorage; logout зовёт эндпоинт.

## Вне рамок
Ротация refresh с server-side blacklist/`token_version` (отдельный долг — отзыв при logout/смене пароля); rate-limiting логина (отдельный долг). Эти два — следующий security-заход после B.
