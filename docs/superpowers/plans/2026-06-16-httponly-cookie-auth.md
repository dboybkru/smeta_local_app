# httpOnly-cookie аутентификация + CSRF — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). Tasks sequential (общие файлы auth).

**Goal:** Перенести сессию из localStorage в httpOnly-cookie (Lax+Secure) + double-submit CSRF; backend читает access из cookie ИЛИ Bearer-заголовка (тесты/API живут); Яндекс-callback на cookie вместо URL-fragment.

**Architecture:** Cookie-хелпер `app/auth/cookies.py`; `get_current_user` читает cookie-или-Bearer; CSRF-middleware проверяет `X-CSRF-Token`==cookie ТОЛЬКО при cookie-аутентификации (Bearer иммунен); login/register/refresh/logout/yandex ставят/чистят cookie и возвращают `UserOut`.

**Tech Stack:** FastAPI + Starlette middleware + pytest (TestClient cookie jar); React 19 + Vitest. Без миграций.

**Спек:** `docs/superpowers/specs/2026-06-16-httponly-cookie-auth-design.md`

**Команды:** backend (из `backend`): `./.venv/Scripts/python.exe -m pytest -q`, `./.venv/Scripts/ruff.exe check .`. frontend (из `frontend`): `npm run test`, `npm run build`, `npm run lint`.

**⚠ Тесты и Secure:** Starlette TestClient ходит по http → Secure-cookie не вернётся. `conftest.py` ДОЛЖЕН выставить `os.environ["COOKIE_SECURE"]="false"` ДО импорта app (рядом с `JOBS_WORKER_DISABLED`), иначе cookie-тесты не пройдут.

---

## Структура файлов
- Создать: `backend/app/auth/cookies.py`.
- Изменить: `backend/app/core/config.py` (cookie_secure), `backend/app/auth/deps.py` (get_current_user cookie-or-header), `backend/app/auth/router.py` (login/register/refresh/logout/yandex + `_user_out` хелпер), `backend/app/main.py` (CSRF-middleware), `backend/tests/conftest.py` (COOKIE_SECURE=false).
- Фронт: `frontend/src/api/client.ts` (переписать), `frontend/src/auth/AuthContext.tsx`, `frontend/src/pages/AuthCallbackPage.tsx`.
- Тесты: `backend/tests/test_auth_cookies.py` (новый), `backend/tests/test_csrf.py` (новый); фронт — правки существующих + новые кейсы client.

---

## Task 1: Cookie-инфра + config + deps + эндпоинты login/register/refresh/logout

**Files:** Create `backend/app/auth/cookies.py`. Modify `backend/app/core/config.py`, `backend/app/auth/deps.py`, `backend/app/auth/router.py`, `backend/tests/conftest.py`. Test `backend/tests/test_auth_cookies.py`.

- [ ] **Step 1: conftest — COOKIE_SECURE=false.** В `backend/tests/conftest.py` рядом с установкой `JOBS_WORKER_DISABLED` (до `from app.main import app`) добавить:
```python
os.environ.setdefault("COOKIE_SECURE", "false")
```
(Если `import os` отсутствует — добавить.)

- [ ] **Step 2: Failing test** `backend/tests/test_auth_cookies.py`:
```python
from app.auth.models import User
from app.core.security import hash_password
from app.orgs.models import Organization


def _active_user(db, email="ck@x.ru", pw="Pass12345"):
    o = Organization(name="CK"); db.add(o); db.commit()
    u = User(email=email, name="U", role="org_admin", status="active",
             org_id=o.id, password_hash=hash_password(pw))
    db.add(u); db.commit(); return u


def test_login_sets_httponly_cookies_and_returns_user(client, db_session):
    _active_user(db_session)
    r = client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "ck@x.ru"  # UserOut, не токены
    # access/refresh httpOnly, csrf — нет
    cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else [r.headers["set-cookie"]]
    joined = " ".join(cookies)
    assert "access_token=" in joined and "HttpOnly" in joined
    assert "csrf_token=" in joined


def test_me_via_cookie(client, db_session):
    _active_user(db_session)
    client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    # cookie jar TestClient уже держит cookie
    r = client.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["email"] == "ck@x.ru"


def test_refresh_via_cookie(client, db_session):
    _active_user(db_session)
    client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["email"] == "ck@x.ru"


def test_logout_clears_cookies(client, db_session):
    _active_user(db_session)
    client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    # logout — cookie-auth, нужен CSRF-заголовок (см. Task 2); шлём из cookie
    csrf = client.cookies.get("csrf_token")
    r = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf} if csrf else {})
    assert r.status_code == 204
    # после logout /me не пускает
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
```
NOTE: TestClient (`client`) использует общий cookie-jar — после login cookie держатся. Проверь, как фикстура `client` устроена (`TestClient(app)`), и что httpx-jar сохраняется между запросами одного клиента.

- [ ] **Step 3: Run → FAIL** `./.venv/Scripts/python.exe -m pytest tests/test_auth_cookies.py -q`.

- [ ] **Step 4: config.** В `backend/app/core/config.py` добавить в `Settings`:
```python
    cookie_secure: bool = True
```

- [ ] **Step 5: cookies.py** — `backend/app/auth/cookies.py`:
```python
import secrets

from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"


def set_auth_cookies(response: Response, access: str, refresh: str) -> str:
    """Ставит access/refresh (httpOnly) + csrf (JS-видимый). Возвращает csrf-токен."""
    csrf = secrets.token_urlsafe(32)
    secure = settings.cookie_secure
    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=secure, samesite="lax",
        path="/api", max_age=settings.access_token_ttl_minutes * 60,
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh, httponly=True, secure=secure, samesite="lax",
        path="/api/auth", max_age=settings.refresh_token_ttl_days * 86400,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="lax",
        path="/", max_age=settings.refresh_token_ttl_days * 86400,
    )
    return csrf


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")
```

- [ ] **Step 6: deps — cookie-or-header.** В `backend/app/auth/deps.py` `get_current_user` переписать (добавить `Request` в импорт fastapi):
```python
def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if token is None and creds is not None:
        token = creds.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Нет токена", headers=_WWW)
    try:
        payload = decode_token(token, expected_type="access")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный токен", headers=_WWW)
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден", headers=_WWW)
    return user
```

- [ ] **Step 7: router — `_user_out` + login/register/refresh/logout.** В `backend/app/auth/router.py`:
  - Добавить импорты: `from fastapi import ... Response` (дополнить существующую строку fastapi-импорта), `from app.auth.cookies import clear_auth_cookies, set_auth_cookies`.
  - Добавить хелпер (после `_yandex_creds`):
```python
def _user_out(db: Session, user: User) -> UserOut:
    org_name: str | None = None
    if user.org_id is not None:
        org = db.get(Organization, user.org_id)
        if org is not None:
            org_name = org.name
    return UserOut(
        id=user.id, email=user.email, name=user.name, role=user.role,
        status=user.status, is_superuser=user.is_superuser,
        org_id=user.org_id, org_name=org_name,
    )
```
  - `me` переписать на `return _user_out(db, user)`.
  - `register` →:
```python
@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = service.register_user(db, body.email, body.password, body.name)
    except service.EmailTakenError:
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")
    if user.status == "active":
        t = service.issue_tokens(user)
        set_auth_cookies(response, t["access_token"], t["refresh_token"])
    return _user_out(db, user)
```
  - `login` →:
```python
@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = service.authenticate(db, body.email, body.password)
    except service.InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    t = service.issue_tokens(user)
    set_auth_cookies(response, t["access_token"], t["refresh_token"])
    return _user_out(db, user)
```
  - `refresh` →:
```python
@router.post("/refresh", response_model=UserOut)
def refresh(
    request: Request,
    response: Response,
    body: RefreshIn | None = None,
    db: Session = Depends(get_db),
):
    token = request.cookies.get("refresh_token") or (body.refresh_token if body else None)
    if not token:
        raise HTTPException(status_code=401, detail="Нет refresh-токена",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(token, expected_type="refresh")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен",
                            headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, int(payload["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен",
                            headers={"WWW-Authenticate": "Bearer"})
    t = service.issue_tokens(user)
    set_auth_cookies(response, t["access_token"], t["refresh_token"])
    return _user_out(db, user)
```
  - Добавить `logout`:
```python
@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_auth_cookies(response)
```

- [ ] **Step 8: Run** `./.venv/Scripts/python.exe -m pytest tests/test_auth_cookies.py tests/test_auth_register_login.py tests/test_auth_me_refresh.py -q` → PASS. ⚠ `test_logout_clears_cookies` зависит от CSRF (Task 2) — пока CSRF-middleware нет, logout пройдёт и так; после Task 2 перепроверить. Существующие Bearer-тесты (`test_auth_*`) должны остаться зелёными (cookie-or-header). Lint `./.venv/Scripts/ruff.exe check .` чисто.

- [ ] **Step 9: Commit**
```bash
git add backend/app/auth/cookies.py backend/app/core/config.py backend/app/auth/deps.py backend/app/auth/router.py backend/tests/conftest.py backend/tests/test_auth_cookies.py
git commit -m "feat(auth): httpOnly-cookie сессия (login/register/refresh/logout) + cookie-or-Bearer в deps"
```
(трейлер Co-Authored-By)

---

## Task 2: CSRF-middleware

**Files:** Modify `backend/app/main.py`. Test `backend/tests/test_csrf.py`.

- [ ] **Step 1: Failing test** `backend/tests/test_csrf.py`:
```python
from app.auth.models import User
from app.core.security import create_access_token, hash_password
from app.orgs.models import Organization


def _user(db):
    o = Organization(name="CS"); db.add(o); db.commit()
    u = User(email="cs@x.ru", name="U", role="org_admin", status="active",
             org_id=o.id, password_hash=hash_password("Pass12345"))
    db.add(u); db.commit(); return u


def test_cookie_mutation_without_csrf_403(client, db_session):
    _user(db_session)
    client.post("/api/auth/login", json={"email": "cs@x.ru", "password": "Pass12345"})
    client.cookies.pop("csrf_token", None)  # эмулируем отсутствие заголовка/несовпадение
    # мутация под cookie-аутентификацией без X-CSRF-Token → 403
    r = client.post("/api/orgs", json={"name": "X"})  # без X-CSRF-Token
    assert r.status_code == 403


def test_cookie_mutation_with_csrf_ok(client, db_session):
    u = _user(db_session)
    client.post("/api/auth/login", json={"email": "cs@x.ru", "password": "Pass12345"})
    csrf = client.cookies.get("csrf_token")
    # superuser нужен для POST /orgs — у обычного org_admin будет 403 по правам, не по CSRF;
    # поэтому проверяем, что С верным CSRF мы НЕ получаем 403-CSRF (получим 403-права или 201)
    r = client.post("/api/orgs", json={"name": "X"}, headers={"X-CSRF-Token": csrf})
    assert r.status_code != 403 or "CSRF" not in r.text


def test_bearer_mutation_without_csrf_ok(client, db_session):
    u = _user(db_session)
    # Bearer-аутентификация (как в существующих тестах) — CSRF не требуется
    hdr = {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
    r = client.patch("/api/profile", json={"org_name": "Z"}, headers=hdr)
    assert r.status_code != 403  # не режется CSRF (права org_admin на PUT профиля есть)
```
NOTE: подбери для теста эндпоинт-мутацию, доступную роли по правам, чтобы 403 был ТОЛЬКО от CSRF. `PUT /api/profile` доступен org_admin — удобно для bearer-кейса. Для cookie-403-кейса любой POST под cookie без заголовка даёт 403-CSRF раньше проверки прав (middleware до роутера). Адаптируй ассерты под фактические маршруты, прочитав роутеры.

- [ ] **Step 2: Run → FAIL** (middleware нет → мутация без CSRF проходит).

- [ ] **Step 3: Middleware.** В `backend/app/main.py` добавить (до `app.include_router`):
```python
from starlette.requests import Request
from starlette.responses import JSONResponse

_CSRF_EXEMPT = {
    "/api/auth/login", "/api/auth/register", "/api/auth/refresh",
    "/api/auth/yandex/login", "/api/auth/yandex/callback",
}
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    path = request.url.path
    if (
        request.method in _UNSAFE_METHODS
        and path.startswith("/api/")
        and path not in _CSRF_EXEMPT
        and request.cookies.get("access_token") is not None
    ):
        cookie = request.cookies.get("csrf_token")
        header = request.headers.get("x-csrf-token")
        if not cookie or not header or cookie != header:
            return JSONResponse(
                {"detail": "CSRF-токен отсутствует или неверен"}, status_code=403
            )
    return await call_next(request)
```
(`@app.middleware("http")` объявить ПОСЛЕ `app = FastAPI(...)` и до include_router; FastAPI применит ко всем запросам.)

- [ ] **Step 4: Run** `./.venv/Scripts/python.exe -m pytest tests/test_csrf.py tests/test_auth_cookies.py -q` → PASS (logout-тест из Task 1 теперь требует X-CSRF — он его уже шлёт). Полный прогон `./.venv/Scripts/python.exe -m pytest -q` → существующие Bearer-тесты зелёные (CSRF их не трогает). Lint чисто.

- [ ] **Step 5: Commit**
```bash
git add backend/app/main.py backend/tests/test_csrf.py
git commit -m "feat(auth): CSRF-middleware (double-submit, только для cookie-аутентификации)"
```

---

## Task 3: Яндекс-callback на cookie вместо URL-fragment

**Files:** Modify `backend/app/auth/router.py`. Test `backend/tests/test_auth_yandex.py`.

- [ ] **Step 1: Failing test** — добавить в `backend/tests/test_auth_yandex.py` кейс (мокая yandex как в существующих тестах файла — прочитать, как они мокают `exchange_code`/`fetch_userinfo`):
```python
def test_yandex_callback_sets_cookies_no_fragment(client, db_session, monkeypatch):
    # настроить мок yandex.exchange_code/fetch_userinfo как в соседних тестах файла,
    # и валидный state-cookie (как делают существующие callback-тесты)
    # ... arrange ...
    r = client.get("/api/auth/yandex/callback?code=c&state=s", follow_redirects=False)
    assert r.status_code in (302, 307)
    loc = r.headers["location"]
    assert "/auth/callback" in loc and "#" not in loc  # без fragment
    assert "access_token=" in " ".join(
        r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list")
        else [r.headers.get("set-cookie", "")]
    )
```
Прочитай существующий `test_auth_yandex.py` и переиспользуй его arrange (state-cookie + моки). Если структура иная — адаптируй ассерты, сохранив суть: redirect без fragment + Set-Cookie access_token.

- [ ] **Step 2: Run → FAIL** (сейчас токены в fragment, cookie не ставятся).

- [ ] **Step 3: Реализация.** В `backend/app/auth/router.py` `yandex_callback` заменить хвост (после `user = service.get_or_create_yandex_user(...)` и проверки blocked):
```python
    t = service.issue_tokens(user)
    resp = RedirectResponse(f"{settings.frontend_url}/auth/callback")
    set_auth_cookies(resp, t["access_token"], t["refresh_token"])
    resp.delete_cookie("yx_state")
    return resp
```
(Убрать формирование `url` с `#access_token=...`.)

- [ ] **Step 4: Run** `./.venv/Scripts/python.exe -m pytest tests/test_auth_yandex.py -q` → PASS. Lint чисто.

- [ ] **Step 5: Commit**
```bash
git add backend/app/auth/router.py backend/tests/test_auth_yandex.py
git commit -m "feat(auth): Яндекс-callback ставит cookie и редиректит без токенов в URL-fragment"
```

---

## Task 4: Фронтенд — client.ts без localStorage + CSRF-заголовок + AuthContext/Callback

**Files:** Modify `frontend/src/api/client.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/pages/AuthCallbackPage.tsx`. Tests: правки существующих + новые кейсы.

- [ ] **Step 1: Переписать `frontend/src/api/client.ts`** — убрать `getTokens/setTokens/clearTokens` и Bearer; добавить `getCsrf()` + `credentials`:
```typescript
const BASE = "/api";

export function getCsrf(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function rawRequest(path: string, options: RequestInit = {}) {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const method = (options.method ?? "GET").toUpperCase();
  if (UNSAFE.has(method)) {
    const csrf = getCsrf();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  return fetch(`${BASE}${path}`, { ...options, headers, credentials: "same-origin" });
}

let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const resp = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
  });
  return resp.ok;
}

export async function tryRefresh(): Promise<boolean> {
  if (refreshing !== null) return refreshing;
  refreshing = doRefresh().finally(() => { refreshing = null; });
  return refreshing;
}
```
СОХРАНИТЬ без изменений: `ApiError`, `formatDetail`, `api`, `apiUpload` (они используют `rawRequest`/`tryRefresh`). Удалить экспорт `getTokens/setTokens/clearTokens`.

- [ ] **Step 2: AuthContext.** В `frontend/src/auth/AuthContext.tsx`:
  - Убрать импорт `clearTokens, getTokens, setTokens` (оставить `api`).
  - `loadMe` catch → просто `setUser(null)` (без clearTokens).
  - `useEffect` → всегда `void loadMe()` (cookie может быть; 401 → null). Убрать `getTokens().access` проверку.
  - `loginWithPassword` → `setUser(await api<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }))` (login теперь возвращает UserOut).
  - Заменить `acceptTokens` на `reload: () => Promise<void>` (просто `loadMe`); обновить тип `AuthState`.
  - `logout` → `async () => { try { await api("/auth/logout", { method: "POST" }); } catch {} setUser(null); }`.

- [ ] **Step 3: AuthCallbackPage.** `frontend/src/pages/AuthCallbackPage.tsx` — убрать парсинг fragment; cookie уже стоят от callback:
```tsx
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function AuthCallbackPage() {
  const { reload } = useAuth();
  const navigate = useNavigate();
  const handled = useRef(false);
  useEffect(() => {
    if (handled.current) return;
    handled.current = true;
    void reload().then(() => navigate("/", { replace: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div className="p-8 text-stone-500">Входим…</div>;
}
```

- [ ] **Step 4: Починить потребителей и тесты.** Grep `acceptTokens`, `getTokens`, `setTokens`, `clearTokens` по `frontend/src` — обновить все (тест-стабы `useAuth` заменить `acceptTokens` на `reload`). Существующие тесты client/AuthContext, которые мокали localStorage/токены — переписать под cookie (мок `document.cookie` для csrf; мок `fetch`). Добавить кейс: `client` шлёт `X-CSRF-Token` на POST когда есть csrf-cookie; не шлёт на GET.

- [ ] **Step 5: Run** (из `frontend`): `npm run test` зелёное, `npm run build` ок, `npm run lint` 0 ошибок.

- [ ] **Step 6: Commit**
```bash
git add frontend/src
git commit -m "feat(ui): cookie-сессия — client.ts без localStorage + X-CSRF на мутациях + reload в AuthContext"
```

---

## Финальная проверка
- [ ] Backend `pytest -q` + `ruff check .` зелёные; фронт `npm run test`/`build`/`lint` зелёные.
- [ ] Спек-ревью + ревью качества (субагентно), фокус: CSRF только при cookie-auth (Bearer не режется); cookie httpOnly/Lax/Secure(конфиг); Яндекс без fragment; нет работы с токенами в JS.
- [ ] Деплой: на проде `COOKIE_SECURE` НЕ задавать (дефолт true) — HTTPS есть. Локальный dev (vite http) — `COOKIE_SECURE=false` в backend env.
