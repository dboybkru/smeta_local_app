# Фаза 4b-2b — Админ-UI конфигурации AI (фронтенд): дизайн

> Брейншторм-дизайн, 2026-06-13. Вторая (последняя) под-фаза 4b-2. Даёт интерфейс к готовому бэкенду `/api/ai/*` (слой AI-провайдеров): подключение провайдеров, импорт/настройка моделей, назначение моделей на цели, советник. Закрывает фазу 4b.

## Цель

Дать админу из интерфейса: завести провайдера (base_url + ключ), импортировать его модели, проставить цены/сильные стороны, назначить primary+fallback модель каждой цели — чтобы AI-генерация КП (и будущий ассистент) заработали без ручных запросов к API. Сейчас всё это доступно только через `/api/ai/*` curl'ом под admin.

## Бэкенд — без изменений

Готов в слое AI-провайдеров. Используемые эндпоинты (все под `require_admin`, префикс `/api/ai`):

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/providers` | список провайдеров (`ProviderOut`: `id,name,base_url,auth_style,enabled,has_key`) |
| POST | `/providers` | создать (`ProviderIn`: `name,base_url,auth_style:"bearer"\|"x_api_key",api_key,enabled`) → 201 |
| PUT | `/providers/{id}` | обновить (`ProviderUpdate`: все поля опц.; `api_key` пустой/нет = не менять) |
| DELETE | `/providers/{id}` | удалить → 204 |
| POST | `/providers/{id}/models/refresh` | автоимпорт моделей → `{imported: N}` |
| GET | `/models?provider_id=` | список моделей (`ModelOut`: `id,provider_id,model_id,label,input_price,output_price,strengths,enabled`) |
| PUT | `/models/{id}` | обновить (`ModelUpdate`: `label,input_price,output_price,strengths,enabled`) |
| DELETE | `/models/{id}` | удалить → 204 |
| GET | `/purposes` | список целей (`PurposeOut`: `id,key,title,description,primary_model_id,fallback_model_id,enabled`) |
| PUT | `/purposes/{key}` | обновить (`PurposeUpdate`: `title,description,primary_model_id,fallback_model_id,enabled`) |
| POST | `/router/recommend` | советник → `list[{purpose_key,provider,model_id,rationale}]` (по ВСЕМ целям сразу; 503 если не настроен, 502 при ошибке LLM) |
| POST | `/purposes/{key}/test` | смоук-тест цели → `{ok: bool, detail: str}` (не бросает, всегда 200) |

Деньги (`input_price`/`output_price`) — `Decimal`, на фронте строки. Ключ провайдера write-only (в ответах только `has_key`).

## Фронтенд

Стек/паттерны как 2b/3b/4b-1. Доступ: всё под admin (страница + ссылка только admin, как «Поставщики»/«Уровни цен»; бэкенд уже `require_admin`).

**Раскладка (одобрена): одна страница `/admin/ai` с тремя секциями подряд** — «Провайдеры», «Модели», «Цели». **Советник: кнопка у каждой цели** («Подобрать»).

| Файл | Ответственность |
|---|---|
| `src/api/ai.ts` | типизированный слой над `api()`/`apiUpload` нет — обычный JSON; все вызовы выше |
| `src/pages/AiConfigPage.tsx` | `/admin/ai`: сборка трёх секций, общий стейт + reload |
| `src/components/ai/ProvidersSection.tsx` | список провайдеров + форма добавления + правка/удаление/refresh |
| `src/components/ai/ModelsSection.tsx` | список моделей (фильтр по провайдеру) + инлайн-правка цены/сильных сторон/enabled + удаление |
| `src/components/ai/PurposesSection.tsx` | список целей + выбор primary/fallback модели + кнопка «Подобрать» (советник) + смоук-тест |
| `src/App.tsx` | + маршрут `/admin/ai` под `RequireAuth` |
| `src/components/AppHeader.tsx` | + ссылка «AI» (admin) рядом с «Поставщики» |

### `api/ai.ts` — типы и функции

Типы зеркалят `ModelOut`/`ProviderOut`/`PurposeOut`/`Recommendation`. Деньги — строки (`input_price: string | null`). Функции:
`listProviders()`, `createProvider(body)`, `updateProvider(id, patch)`, `deleteProvider(id)`,
`refreshModels(providerId)` (→ `{imported}`), `listModels(providerId?)`, `updateModel(id, patch)`, `deleteModel(id)`,
`listPurposes()`, `updatePurpose(key, patch)`, `recommend()` (→ `Recommendation[]`), `testPurpose(key)` (→ `{ok, detail}`).
`createProvider`/`updateProvider` шлют `api_key` строкой; пустая строка в update = не менять ключ (как на бэке).

### ProvidersSection

- Список: имя · base_url · auth_style · «ключ задан»/«нет ключа» (по `has_key`) · вкл/выкл.
- Форма «Добавить»: имя, base_url, auth_style (select bearer/x_api_key), api_key (password-инпут), enabled (по умолч. вкл) → `createProvider` → reload.
- На строке: «Импорт моделей» (`refreshModels` → тост «Импортировано N»), «Изменить» (правка base_url/auth_style/нового ключа/enabled — простая инлайн-форма или `window.prompt` для MVP — см. план), «Удалить» (`deleteProvider`, confirm).
- Подсказка по известным провайдерам: AITunnel `https://api.aitunnel.ru/v1/` (bearer), VseGPT `https://api.vsegpt.ru/v1` (x_api_key) — текстом под формой.

### ModelsSection

- Фильтр по провайдеру (select «все / <провайдер>»), `listModels(providerId?)`.
- Таблица: провайдер · model_id · label · вход.цена · исх.цена · сильные стороны · вкл.
- Инлайн-правка: `label`, `input_price`, `output_price`, `strengths` (по blur → `updateModel`), `enabled` (чекбокс). Цены — строковые инпуты, пустое → `null`.
- «Удалить» (confirm).
- Пустой список → подсказка «Моделей нет — добавьте провайдера и нажмите „Импорт моделей“».

### PurposesSection

- Таблица целей: title (`key` мелким) · primary-модель (select из enabled моделей) · fallback-модель (select, опц., «— нет —») · вкл.
- Выбор модели → `updatePurpose(key, {primary_model_id})` (или fallback) → reload. Select показывает `«<провайдер> / <label>»`; значение = `AIModel.id`.
- **Кнопка «Подобрать» у каждой цели**: первый клик (на любой строке) вызывает `recommend()` один раз, результат кэшируется в стейте; затем по каждой цели показывается её рекомендация (`provider` / `model_id` + `rationale`) с кнопкой «Применить». «Применить» мапит `(provider, model_id)` рекомендации → `AIModel.id` (по загруженным моделям: совпадение `model.model_id === rec.model_id` И провайдер по имени) → `updatePurpose(key, {primary_model_id})`. Если модель из рекомендации не найдена среди импортированных — подсказка «Сначала импортируйте модели этого провайдера». `recommend()` 503 → плашка «Советник недоступен: цель router не настроена»; 502 → тост.
- «Тест» у каждой цели: `testPurpose(key)` → бейдж ✓/✗ + `detail` (на 200 всегда; `{ok:false}` показывает причину «AI не настроен»/ошибку).

### AppHeader

Ссылка «AI» → `/admin/ai`, видна только admin (`isAdmin`), рядом с «Поставщики».

## Тестирование (Vitest, мок fetch + мок useAuth, паттерн 2b/3b/4b-1)

- `api/ai.ts`: по желанию покрыть тонкие места (мапинг рекомендации) на уровне компонента, отдельный тест слоя не обязателен.
- `ProvidersSection`: рендер списка (`has_key` → «ключ задан»); добавление (POST → провайдер появился); refresh (POST → тост с N).
- `ModelsSection`: рендер таблицы; правка цены (blur → PUT с новым `input_price`); enabled-чекбокс (PUT).
- `PurposesSection`: рендер; смена primary (select → PUT `primary_model_id`); «Подобрать» (recommend → у цели показана рекомендация + «Применить» → PUT смапленным id); 503 → плашка.
- `AppHeader`: «AI» видна admin, скрыта у estimator/viewer.
- `npm run test`/`build`/`lint` чисто.

## Решения (зафиксировано)

1. Одна страница `/admin/ai`, три секции подряд (Провайдеры → Модели → Цели).
2. Советник — кнопка «Подобрать» у каждой цели; `recommend()` вызывается один раз и кэшируется, рекомендации раскладываются по строкам.
3. Всё под admin.
4. Ключ провайдера — password-инпут, write-only; в списке только «ключ задан/нет».
5. Деньги (цены моделей) — строки на фронте, пустое = `null`.
6. Правка провайдера в MVP — допустима инлайн-форма ИЛИ `window.prompt` (как rename в PriceLevelsPage), реши в плане проще.

## Отложено (не в 4b-2b)

- Подключение реального провайдера на проде (нужен ключ пользователя + «разрешаю») — отдельный шаг после мержа.
- Рантайм-роутинг / `model:"auto"`, per-user ключи.
- Графики расхода/учёт токенов.
- Интерактивный ассистент (фаза 5) — потребляет `call_llm(purpose="assistant")`.
