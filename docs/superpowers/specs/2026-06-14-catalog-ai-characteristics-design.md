# Каталог — AI-характеристики оборудования: дизайн

> Брейншторм-дизайн, 2026-06-14. Поверх слоя AI (`call_llm`) и учёта расхода. AI извлекает характеристики оборудования из названия позиции и хранит их парами ключ-значение, чтобы ассистент понимал, что подбирает, а клиент — что покупает.

## Решения (зафиксировано в брейншторме)

1. **Хранение:** пары ключ-значение — `CatalogItem.characteristics` JSON `dict[str,str]`, nullable (None = ещё не извлечено).
2. **Источник:** AI извлекает из названия (и unit/kind) позиции — отдельная AI-цель `catalog_extract` (админ назначает дешёвую модель).
3. **Запуск:** авто при импорте — `ImportPage` после успешного импорта сам циклически дёргает batch-эндпоинт, пока есть необработанные; плюс кнопка дозаполнения в каталоге. Пакетно (много позиций за один LLM-вызов), чтобы не упереться в таймаут и цену.
4. **Доступ:** admin (как импорт/каталог-запись). Расход — в «Расходы» (`ai_usage`, purpose=`catalog_extract`).

## Бэкенд

### Модель + миграция
- `CatalogItem.characteristics: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)` (как `Supplier.column_mapping_template`).
- Миграция: `ADD COLUMN characteristics` (nullable) **+** `bulk_insert` новой цели `ai_purposes`: `{key:"catalog_extract", title:"Извлечение характеристик", description:"Извлекает характеристики оборудования из названия позиции (ключ-значение).", enabled:true}`.

### `app/catalog/characteristics.py`
- `EXTRACT_SCHEMA` — `{type:object, properties:{items:{type:array, items:{type:object, properties:{id:{type:integer}, characteristics:{type:object}}}}}}`.
- `extract_batch(db, batch=40, supplier_id=None) -> dict` :
  1. Выбрать до `batch` позиций `WHERE characteristics IS NULL` (опц. `supplier_id`), плюс `remaining` = общее число таких (для прогресса).
  2. Если пусто → `{"processed":0, "remaining":0}`.
  3. Промпт: «Ты — инженер по оборудованию. Для каждой позиции извлеки ключевые технические характеристики из названия в виде пар ключ-значение на русском (например „Разрешение“:„2 Мп“, „Питание“:„PoE“, „Степень защиты“:„IP67“). Если по названию характеристик не определить — пустой объект. Верни JSON {items:[{id, characteristics}]}». Вход: список `{id, name, unit, kind}`.
  4. `call_llm(db, "catalog_extract", [...], json_schema=EXTRACT_SCHEMA, max_tokens=2000)`.
  5. Для каждого вернувшегося `{id, characteristics}` — если позиция в обрабатываемой пачке: записать `characteristics` (dict[str,str]; не-строковые значения привести к str; None→`{}`). Позициям пачки, по которым AI ничего не вернул, поставить `{}` (чтобы не зациклить — считаются обработанными).
  6. `db.commit()`. Вернуть `{"processed": <кол-во в пачке>, "remaining": <осталось NULL после пачки>}`.
- Невалидный ответ LLM → позиции пачки получают `{}` (обработаны), processed=размер пачки. `AINotConfigured`/`AIError` пробрасываются (эндпоинт обработает).

### Эндпоинт `app/catalog/router.py`
- `POST /api/catalog/extract-characteristics` (Form/query `supplier_id?`, `batch=40`), `require_admin` → `{processed, remaining}`. `AINotConfigured` → 503 («цель catalog_extract не настроена»), `AIError` → 502.
- `ItemOut` (+ `characteristics: dict | None`); в `list_items` прокинуть `characteristics=i.characteristics`.

## Фронтенд

| Файл | Изменение |
|---|---|
| `api/catalog.ts` | `CatalogItem` + `characteristics: Record<string,string> \| null`; `extractCharacteristics(supplierId?, batch?)` → `{processed, remaining}` |
| `pages/ImportPage.tsx` | после успешного импорта — авто-цикл извлечения с прогрессом |
| `pages/CatalogPage.tsx` | показать характеристики у позиции (чипсы/свёрнуто); кнопка «AI: извлечь характеристики» (дозаполнение) |
| `backend assistant/service.py` | в кандидаты ассистента добавить ключевые хар-ки (если есть) |

- **ImportPage авто-цикл:** на шаге результата, если импорт прошёл, вызвать `extractCharacteristics(supplierId)` в цикле `while remaining>0`, показывая «✨ AI: обработка характеристик… осталось N». При 503 — показать «AI не настроен — характеристики пропущены», цикл остановить (импорт не ломать). Кап итераций (защита) — напр. 100.
- **CatalogPage:** под/рядом с позицией — характеристики как чипсы `ключ: значение` (свернуть если много). Кнопка «AI: извлечь характеристики» (для позиций без хар-к) — тот же эндпоинт, авто-цикл с прогрессом.
- **Кандидаты ассистента:** в `_candidates` к строке кандидата добавить краткие хар-ки (`it.characteristics`), если заполнены — агент будет понимать оборудование.

## Ошибки / стоимость

- `catalog_extract` не настроена → 503, обработка пропускается (импорт и каталог работают). Расход пишется в «Расходы».
- Пакет 40 позиций/вызов; `characteristics IS NULL` — только новые/неизвлечённые (повторный импорт тех же позиций не переизвлекает, т.к. они не NULL). При желании дозаполнить — кнопка обрабатывает оставшиеся NULL.
- Значения приводятся к строке; пустой объект `{}` означает «AI обработал, характеристик нет» (≠ NULL «не обработано»).

## Тестирование (pytest + Vitest, мок call_llm/fetch)

- **Backend** `characteristics.extract_batch` (мок `call_llm` → возвращает items с парами → у позиций появились characteristics; позиции без ответа → `{}`; remaining уменьшается; пустой набор → `{0,0}`).
- Эндпоинт: `extract-characteristics` → `{processed, remaining}`; не-админ → 403; не настроено → 503.
- `list_items` отдаёт `characteristics`.
- Ассистент: `_candidates` включает хар-ки (мини-тест build).
- **Frontend**: ImportPage авто-цикл (мок: 1-й вызов remaining=1, 2-й remaining=0 → прогресс показан, цикл завершился); CatalogPage показывает чипсы хар-к; кнопка извлечения зовёт эндпоинт.
- Сборка/линт/ruff чисто. Миграция проверяется на боевом Postgres при деплое (boolean не задействован; nullable JSON-колонка безопасна).

## Отложено

- Характеристики в КП/экспорт (Excel/PDF).
- Ручное редактирование пар в каталоге.
- Фильтр/поиск каталога по характеристикам.
- Переизвлечение по кнопке для уже заполненных (сейчас только NULL).
