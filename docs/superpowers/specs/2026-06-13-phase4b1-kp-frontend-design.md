# Фаза 4b-1 — Фронтенд КП-потока: дизайн

> Брейншторм-дизайн (с визуальным компаньоном), 2026-06-13. Под-фаза 1 из 4b. UI для уже задеплоенного бэкенда фазы 4a: профиль исполнителя, редактор блоков КП с AI-генерацией, экспорт Excel/PDF, публичные ссылки. Под-фаза 4b-2 (админ-UI AI-конфига + управление поставщиками) — отдельный спек.

## Цель

«Зажечь» в интерфейсе сквозной сценарий **смета → КП → скачать/поделиться**: сметчик заполняет реквизиты исполнителя один раз, по смете генерирует маркетинговое КП (AI или вручную), скачивает Excel/PDF на нужном уровне и/или отдаёт клиенту публичную ссылку.

## Стек и паттерны (как фаза 3b)

React 19 + TypeScript + Vite + Tailwind v4 + react-router-dom v7; Vitest + @testing-library/react. Слой API над `api()`/`apiUpload` (`src/api/client.ts`). Деньги/qty — строки (Decimal из JSON). Тесты — мок `fetch` + мок `useAuth` (паттерн 3b: AuthProvider + cleanup). Доступ: `canEdit = user.role === "estimator" || user.role === "admin"` (allowlist, как в `useEstimate`).

## Раскладка (одобрено визуально)

**Вкладки на странице сметы** (`EstimateEditorPage`): **Смета** (таблица 3b) · **КП** · **Поделиться**. Профиль исполнителя — отдельная страница `/profile`.

## Компоненты и файлы

| Файл | Ответственность |
|---|---|
| `src/api/profile.ts` | типы + `getProfile()`, `putProfile(body)` над `/api/profile` |
| `src/api/proposals.ts` | типы блоков + `generateProposal(id)`, `patchProposal(id, partial)` |
| `src/api/publicLinks.ts` | типы + `listLinks(id)`, `createLink(id, body)`, `revokeLink(linkId)` |
| `src/api/export.ts` | `downloadExport(id, fmt, level)` — fetch с токеном → Blob → скачивание файла |
| `src/pages/ProfilePage.tsx` | форма реквизитов исполнителя (`/profile`) |
| `src/components/estimate/EstimateTabs.tsx` | переключатель Смета/КП/Поделиться (локальный стейт вкладки) |
| `src/components/estimate/ProposalTab.tsx` | вкладка КП: AI-кнопка + `ProposalBlocksEditor` + плашка «AI не настроен» |
| `src/components/estimate/ProposalBlocksEditor.tsx` | 7 блоков: заголовок/подзаголовок/боль/решение/преимущества(список)/условия/CTA |
| `src/components/estimate/ShareTab.tsx` | вкладка Поделиться: `ExportButtons` + `PublicLinksManager` |
| `src/components/estimate/ExportButtons.tsx` | селектор уровня (full/cover/estimate) + кнопки Excel/PDF |
| `src/components/estimate/PublicLinksManager.tsx` | форма создания + список ссылок (копировать/отозвать) |
| `src/components/AppHeader.tsx` | + ссылка «Реквизиты» → `/profile` (estimator/admin) |
| `src/App.tsx` | + маршрут `/profile` под `RequireAuth` |
| `src/hooks/useEstimate.ts` | переиспользуется; `EstimateDetail` уже несёт `proposal` (или добавить поле в тип) |

`EstimateEditorPage` оборачивает существующую таблицу (3b) во вкладку «Смета», добавляет вкладки «КП» и «Поделиться». Стейт вкладки — локальный (`useState`), без роутинга (проще; deep-link не требуется).

## Профиль исполнителя (`/profile`)

Форма по `ProfileIn`: организация, ИНН, контакты (телефон/email/адрес/сайт — вложенный объект), банковские реквизиты, УТП (список строк +/✕), кейсы (список строк +/✕), гарантия, **логотип — поле URL** (загрузки файла нет; бэкенд хранит `logo_url` строкой). `GET /api/profile` отдаёт пустой профиль до первого сохранения (бэкенд возвращает `id:0`/пустые поля). Сохранение — `PUT /api/profile`, тост/индикатор «Сохранено». Доступ: estimator/admin; viewer не видит ссылку (профиль — реквизиты исполнителя, не клиента).

## Вкладка «КП» (`ProposalTab` + `ProposalBlocksEditor`)

- **AI-генерация:** кнопка «✨ Сгенерировать AI» → `POST /api/estimates/{id}/proposal/generate`. Если у сметы уже есть блоки — `confirm()` «Перезаписать?». Ответ заполняет все 7 блоков. Спиннер на время запроса. Ошибки: **503** → плашка «AI не настроен — заполните вручную или попросите админа подключить провайдера»; **502** → тост «Ошибка AI, попробуйте позже».
- **Ручная правка:** 7 полей; `advantages` — список-чипсы (добавить/удалить). Сохранение блока — `PATCH /api/estimates/{id}/proposal` с изменённым полем (debounce на blur, частичный объект; пустая строка/`[]` допустимы). «🗑 Очистить КП» — `PATCH` с обнулением всех полей (или `confirm` + сброс).
- Доступ: правка/генерация только при `canEdit`; иначе блоки read-only.

## Вкладка «Поделиться» (`ShareTab`)

- **Экспорт** (`ExportButtons`): селектор уровня (`Полное КП` full / `Титул + смета` cover / `Только смета` estimate, по умолчанию full) → «Скачать Excel» / «Скачать PDF». `downloadExport` делает `fetch` к `GET /api/estimates/{id}/export.xlsx|.pdf?level=` с заголовком `Authorization`, читает `Blob`, имя файла из `Content-Disposition` (или `estimate-{id}.xlsx`), триггерит скачивание (`URL.createObjectURL` + `<a download>`). Доступно всем, кто видит смету.
- **Публичные ссылки** (`PublicLinksManager`): форма создания (уровень, срок `expires_at` — пресеты «без срока / 7 / 30 дней», чекбокс «водяной знак» + текст) → `POST /api/estimates/{id}/public-links`. Список (`GET …/public-links`): для каждой — публичный URL `${BACKEND_URL}/p/{token}` (кнопка «Копировать»), уровень, срок, статус; «Отозвать» → `DELETE /api/public-links/{id}` (ставит `revoked`, остаётся в списке как отозванная). Создание/отзыв — только `canEdit`.
- Публичная страница `/p/{token}` уже отдаётся бэкендом (отдельный HTML, не часть SPA) — фронту делать нечего, только давать ссылку.

## Данные/типы

- `Proposal` (на `EstimateDetail`): `{title, subtitle, pain, solution, advantages: string[], terms, cta} | null`. Если в типе `EstimateDetail` поля `proposal` нет — добавить (бэкенд его возвращает в `GET /api/estimates/{id}`; **проверить сериализацию `proposal` в `EstimateDetail` на бэке — при необходимости добавить поле в схему** как мелкую правку).
- `PublicLink`: `{id, token, level, expires_at, watermark_enabled, watermark_text, revoked, created_at}`.
- `Profile`: по `ProfileOut`.
- `BACKEND_URL` для публичных ссылок — из env фронта (Vite `import.meta.env`) или брать `window.location.origin` (на проде совпадает со `smetaapp.ru`). Решение: `window.location.origin` (без новой env).

## Обработка ошибок

- 401 — общий refresh/redirect (есть в `api/client.ts`).
- 403/viewer — UI прячет действия записи (не полагаемся только на бэк).
- 404 чужой сметы — общий guard страницы сметы (3b).
- 503/502 от AI — как описано во вкладке КП.

## Тестирование (Vitest, мок fetch + мок useAuth, паттерн 3b)

- `ProfilePage`: загрузка пустого профиля, заполнение, PUT, добавление/удаление УТП-чипса.
- `ProposalTab`: генерация (мок 200 → блоки заполнились), confirm-перезапись, 503 → плашка, ручная правка → PATCH; viewer → read-only.
- `ProposalBlocksEditor`: advantages add/remove.
- `ExportButtons`: выбор уровня меняет URL запроса; клик → вызов downloadExport (мок Blob).
- `PublicLinksManager`: создать (форма → POST), список рендерится, копировать (clipboard мок), отозвать → DELETE → строка как «отозвана»; viewer не видит create/revoke.
- `AppHeader`: ссылка «Реквизиты» видна estimator/admin.
- Сборка/линт чисто (`npm run build`, `npm run lint`).

## Решения (зафиксировано)

1. Раскладка — вкладки Смета/КП/Поделиться в `EstimateEditorPage`; стейт вкладки локальный.
2. Профиль — отдельная страница `/profile`; логотип — URL-поле (без загрузки).
3. Экспорт+публичные ссылки сведены во вкладку «Поделиться».
4. AI-генерация перезаписывает все блоки (с подтверждением); 503 → плашка, ручной ввод работает.
5. Доступ: запись (КП/ссылки) — estimator-владелец/admin; экспорт — любой видящий смету; viewer read-only.
6. Скачивание — fetch→Blob с токеном (не прямой `<a href>`, т.к. нужен заголовок Authorization).
7. Публичный URL — `${window.location.origin}/p/{token}`.

## Отложено (не в 4b-1)

- Админ-UI AI-конфига + управление поставщиками → 4b-2.
- Загрузка файла логотипа (пока URL).
- Deep-link на вкладку (стейт локальный).
- Предпросмотр КП внутри SPA (есть публичная страница `/p/{token}` от бэкенда).
