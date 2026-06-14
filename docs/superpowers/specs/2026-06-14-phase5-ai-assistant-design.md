# Фаза 5 — Интерактивный AI-ассистент редактора смет: дизайн

> Брейншторм-дизайн, 2026-06-14. Поверх готового слоя AI-провайдеров (`call_llm(purpose="assistant")`) и учёта расхода (`ai_usage`). Агентный ассистент, который по диалогу предлагает изменения сметы пакетом, применяемые по подтверждению.

## Решения (зафиксировано в брейншторме)

1. **Роль:** агентный — ассистент сам формирует изменения сметы (через структурированный changeset).
2. **Применение:** пакетное подтверждение — собирает предложенные операции, показывает, пользователь жмёт «Применить всё»/«Отклонить». Ничего не применяется без подтверждения.
3. **Операции:** полный набор — добавление разделов/позиций каталога/своих строк, изменение кол-ва и цен, удаление строк/разделов, наценка раздела, НДС сметы.
4. **UI:** боковая панель справа (видно таблицу сметы и чат одновременно).
5. **Грунтовка на каталоге:** 2-шаговый retrieval (без function-calling) — LLM выдаёт поисковые термины → бэкенд ищет в каталоге → LLM строит changeset из кандидатов. Надёжно (проверенный `json_schema`), не зависит от tool-calling провайдера.
6. **Доступ:** только `canEdit` (estimator/admin), как мутации сметы.

## Архитектура — модуль `backend/app/assistant/` (по образцу `proposals`)

### `schemas.py`
- `ChatMessage` `{role: "user"|"assistant", content: str}`.
- `ChatRequest` `{messages: list[ChatMessage]}`.
- **Операции** (Pydantic-юнион по полю `op`), `Operation = Annotated[Union[...], Field(discriminator="op")]`:
  - `AddSection` `{op:"add_section", name: str}`
  - `AddCatalogLine` `{op:"add_catalog_line", section_name: str, catalog_item_id: int, qty: Decimal}`
  - `AddCustomLine` `{op:"add_custom_line", section_name: str, name: str, unit: str="шт", qty: Decimal, material_price: Decimal=0, work_price: Decimal=0}`
  - `SetQty` `{op:"set_qty", line_id: int, qty: Decimal}`
  - `SetPrice` `{op:"set_price", line_id: int, material_price: Decimal|None, work_price: Decimal|None}`
  - `DeleteLine` `{op:"delete_line", line_id: int}`
  - `DeleteSection` `{op:"delete_section", section_id: int}`
  - `SetSectionMarkup` `{op:"set_section_markup", section_id: int, markup_percent: Decimal}`
  - `SetVat` `{op:"set_vat", vat_enabled: bool, vat_rate: Decimal|None}`
- `ChatResponse` `{reply: str, operations: list[Operation]}`. (Стоимость отдельно в ChatResponse не возвращаем — `call_llm` пишет расход в `ai_usage`, он виден в разделе «Расходы»; чтобы не тащить cost через слой. Поле можно добавить позже.)
- `ApplyRequest` `{operations: list[Operation]}`.

Деньги/qty — строки на фронте, `Decimal` в Pydantic (как везде).

### `service.py`
- `build_context(estimate) -> str` — компактное текстовое представление сметы для промпта: разделы (id, имя, наценка), строки (id, имя, ед., кол-во, цены), итоги, флаг НДС. Включает **id** строк/разделов, чтобы LLM мог ссылаться на них в `set_qty`/`delete_*`.
- `run_assistant(db, estimate, messages) -> ChatResponse`:
  1. `context = build_context(estimate)`.
  2. **Шаг 1 (retrieval-термины):** `call_llm(db, "assistant", [...], json_schema=SEARCH_SCHEMA)` → `{queries: list[str]}` (системный промпт: «по последнему сообщению пользователя и смете предложи до 5 поисковых запросов по каталогу; пусто — если каталог не нужен»).
  3. **Поиск кандидатов:** для каждого `q` — `catalog.service.search_items(db, q, limit=5)`; собрать уникальные `CatalogItem`, кап ≤ 30; для каждого — цена `snapshot_line_values`-логикой (или `latest_prices_for`) для отображения. Сформировать текст «КАНДИДАТЫ: id|имя|ед|цена».
  4. **Шаг 2 (changeset):** `call_llm(db, "assistant", [...context + кандидаты + диалог...], json_schema=CHANGESET_SCHEMA)` → `{reply: str, operations: [...]}`. Системный промпт описывает доступные операции и правила (ссылаться только на реальные id/кандидатов; раздел — по имени).
  5. Валидировать `operations` Pydantic-юнионом (невалидные — пропустить с пометкой в reply либо 422; решение: пропустить молча, не ломать ответ). Вернуть `ChatResponse` (стоимость — из последнего `ai_usage`-вызова при наличии).
- `apply_changeset(db, estimate, operations) -> None` — **атомарно** (один commit; при ошибке `db.rollback()` + `AIError`/HTTPException). Порядок: сперва `add_section` (создать `EstimateSection`, как в `estimates.router.add_section`: `branch=base_branch`, `sort_order=len(branch.sections)`), построить карту `name -> section` (существующие разделы + новые). Затем строки (`add_catalog_line`: `db.get(CatalogItem)`, `snapshot_line_values`; `add_custom_line` — как ветка `else` в `add_line`), `set_qty`/`set_price` (`get_owned_line`), `delete_line`/`delete_section`, `set_section_markup` (`get_owned_section`), `set_vat` (на `estimate`). Использовать существующие `estimates.service` геттеры для проверки принадлежности.
- `SEARCH_SCHEMA`, `CHANGESET_SCHEMA` — json-схемы (как `PROPOSAL_SCHEMA` в proposals).

### `estimates/service.py` — небольшой рефактор
Вынести построение детали сметы из `estimates.router.get_estimate` в `service.build_estimate_detail(est, user) -> schemas.EstimateDetail` (с сокрытием маржи/закупки по роли). Переиспользовать в `get_estimate` и в `assistant` apply-эндпоинте (DRY).

### `router.py` (`prefix="/api"`, под `require_active` + `require_write`)
- `POST /api/estimates/{id}/assistant/chat` (body `ChatRequest`) → `ChatResponse`. Резолв сметы `get_owned_estimate`+`require_write`. Внутри `run_assistant`. `AINotConfigured` → 503, `AIError` → 502.
- `POST /api/estimates/{id}/assistant/apply` (body `ApplyRequest`) → `EstimateDetail`. `require_write`, `apply_changeset`, вернуть `build_estimate_detail`.
- Регистрация роутера в `app.main`.

Расход AI пишется автоматически (`call_llm` → `record_usage`, purpose="assistant") — попадёт в раздел «Расходы».

## Фронтенд

| Файл | Ответственность |
|---|---|
| `src/api/assistant.ts` | типы (ChatMessage/Operation/ChatResponse) + `chatAssistant(id, messages)`, `applyChangeset(id, operations)` |
| `src/components/estimate/AssistantPanel.tsx` | выезжающая панель справа: чат, ввод, ChangesetPreview, «Применить всё»/«Отклонить» |
| `src/pages/EstimateEditorPage.tsx` | кнопка «✨ Ассистент» (canEdit) + рендер `AssistantPanel`; `onApplied` → `e.reload()` |
| `src/hooks/useEstimate.ts` | добавить публичный `reload()` (если нет) для обновления после применения |

- **AssistantPanel:** фикс-панель справа (`fixed right-0 inset-y-0 w-[420px]`, оверлей), кнопка закрытия. Локальный стейт `messages` (эфемерный). Отправка → `chatAssistant` → добавить ответ ассистента + сохранить `operations` последнего ответа. **ChangesetPreview** — человекочитаемый список операций (напр. «➕ Раздел „Оборудование“», «➕ С2000-4 × 4 в „Оборудование“», «✏️ кол-во строки #12 → 4», «🗑 удалить строку #15»). Кнопки «Применить всё» → `applyChangeset(id, ops)` → `onApplied(detail)` → reload + очистить pending changeset; «Отклонить» → сбросить changeset.
- Состояния: загрузка (спиннер «Думаю…»), 503 → плашка «AI не настроен», 502/ошибка → тост. Пустой `operations` → только текст ответа.
- Стоимость: если `cost_rub` пришёл — мелким «потрачено X ₽».
- Доступ: панель/кнопка только при `canEdit`.

## Ошибки / стоимость / производительность

- 2 LLM-вызова на сообщение (ограничено), `max_tokens` разумный (напр. 1500). Стоимость учитывается в `ai_usage`.
- `apply_changeset` атомарен: любая ошибка операции → откат всего пакета + сообщение, смета не испорчена.
- Невалидные/недостижимые ссылки (`line_id`/`section_id` чужие/несуществующие) → `get_owned_*` бросает 404 → пакет откатывается; reply честно сообщает.
- Каталог-кандидаты кап ≤ 30, поисковых терминов ≤ 5 — ограничение размера промпта/стоимости.

## Тестирование (pytest + Vitest, мок `call_llm`/fetch)

**Backend** (мок `ai_service.call_llm`: 1-й вызов → `{queries:[...]}`, 2-й → `{reply, operations}`; реальный catalog search на sqlite):
- `run_assistant`: возвращает reply + валидированные операции; пустые queries → пропуск поиска; чистый вопрос (пустой changeset).
- `apply_changeset`: add_section+add_catalog_line по имени раздела (новый раздел в том же пакете) → строка создана со снапшот-ценой; set_qty/set_price/delete мутируют; set_vat; **атомарность** — битая операция откатывает весь пакет (смета без изменений).
- Эндпоинты: `chat` (мок AI) → reply+operations; `apply` → обновлённый EstimateDetail; `viewer` → 403; не настроен AI → 503.
- `build_estimate_detail` рефактор не ломает `get_estimate` (существующие тесты зелёные).

**Frontend** (паттерн 2b/3b/4b):
- `AssistantPanel`: открытие; отправка сообщения (мок fetch chat) → ответ + ChangesetPreview виден; «Применить всё» (мок apply) → вызван `applyChangeset` + `onApplied`; 503 → плашка; пустой changeset → только текст.

**Сборка/линт чисто; миграций НЕТ** (новых таблиц нет — диалог эфемерный).

## Отложено (не в MVP)

- Сохранение истории диалога (таблица conversations) — эфемерный чат в MVP.
- Function-calling / настоящий tool-loop.
- Потоковый вывод (SSE).
- Превью изменений прямо в таблице сметы (подсветка) — пока список в панели.
- Откат применённого пакета (undo) — есть ручное редактирование.
