# Характеристики: импорт-колонка + фильтр каталога: дизайн

> Брейншторм-дизайн, 2026-06-14. Расширяет фичу характеристик: (1) колонка характеристик при импорте прайса → сырой текст в каталог; (2) AI раскидывает сырьё в фильтруемые признаки (свободные ключи + единая терминология); (3) фильтр каталога по признакам.

## Решения (зафиксировано)

1. **Источник:** при импорте прайса можно указать **колонку характеристик** → сырой текст хранится в `CatalogItem.characteristics_raw`.
2. **Структурирование:** существующая AI-цель `catalog_extract` берёт источником `characteristics_raw` (если есть, иначе name) и раскладывает в `characteristics` (JSON ключ-значение). **Свободные ключи + AI-нормализация** — промпт просит единую русскую терминологию (Разрешение, Объектив, Температурный режим, Степень защиты, Питание…).
3. **Фильтр:** каталог фильтруется по признакам; список доступных признаков (ключ→значения) строится из фактически встретившихся (эндпоинт facets).

## Бэкенд

### Модель + миграция
- `CatalogItem.characteristics_raw: Mapped[str | None]` (`Text`, nullable). Миграция: add column.
- `characteristics_text` НЕ вводим — фильтр по JSON напрямую (см. ниже).

### Импорт
- `ColumnMapping.characteristics_col: int | None = None`.
- `ParsedRow.characteristics: str = ""`; `parse_rows`: `characteristics=_cell(row, mapping.characteristics_col)`.
- `import_parsed`: при создании/обновлении — `raw = row.characteristics`; если `raw` непустой:
  - создать: `characteristics_raw=raw`;
  - обновить: если `raw != item.characteristics_raw` → `item.characteristics_raw = raw` И `item.characteristics = None` (сбросить, чтобы AI переизвлёк по новому сырью).
- `ColumnMapper` (фронт): селектор «Характеристики» (как «Категория»).

### AI-структурирование (catalog_extract)
- `characteristics.extract_batch`: источник для позиции = `it.characteristics_raw or it.name`; в payload передавать поле `text`.
- Промпт: «Извлеки технические характеристики из описания/названия в пары ключ-значение на русском. Используй ЕДИНУЮ терминологию ключей (Разрешение, Объектив, Фокусное расстояние, Температурный режим, Степень защиты, Питание, Матрица…) — одинаковые понятия = одинаковый ключ. Значения кратко. Нет данных → {}».
- Логика «обработан = characteristics не NULL» сохраняется (re-extract при сбросе в NULL).

### Фильтр и фасеты
- `GET /api/catalog/facets?supplier_id=&kind=` (`require_active`) → агрегирует `characteristics` по отфильтрованным позициям (Python, кап 2000 позиций), возвращает `{key: [значения, отсортированы, уникальны, кап 50 на ключ]}` для построения UI-фильтра. Кап числа ключей ~40.
- `search_items(..., facets: dict[str,str] | None = None)`: для каждой пары (k, v) добавить условие `CatalogItem.characteristics[k].as_string() == v` (кросс-БД JSON-доступ SQLAlchemy; обязателен SQLite-тест, иначе fallback `cast(CatalogItem.characteristics[k], String)`).
- `GET /api/catalog/items`: принять повторяемый query-параметр `f` вида `Ключ=Значение` (несколько) → распарсить в `facets` dict → передать в `search_items`.

## Фронтенд

| Файл | Изменение |
|---|---|
| `api/catalog.ts` | `ColumnMapping.characteristics_col`; `listItems` принимает `facets?: Record<string,string>` → query `f=K=V`; `getFacets(supplier_id?, kind?)` → `Record<string,string[]>` |
| `components/ColumnMapper.tsx` | селектор «Характеристики» (как category_col) |
| `pages/CatalogPage.tsx` | загрузка фасетов (по текущему supplier/kind) → блок фильтров (для каждого ключа — `<select>` значений); выбранные фасеты → в `listItems`; сброс фасетов при смене supplier/kind |

- CatalogPage: под строкой поиска — компактные выпадашки фасетов («Разрешение: любое/2 Мп/4 Мп», …). Выбор → перезапрос items с `facets`. «Сбросить фильтры». Фасеты тянутся при изменении supplier/kind.

## Ошибки/edge

- Нет колонки характеристик при импорте → ничего не ломается (старое поведение).
- AI не настроен → характеристики не извлекаются (как раньше), фильтр пуст — каталог работает.
- Повторный импорт того же сырья → `characteristics` не сбрасывается (raw не изменился) → нет лишнего AI-расхода.
- Кросс-БД JSON-фильтр обязателен к покрытию SQLite-тестом.

## Тестирование (pytest + Vitest)

- **Backend:** ColumnMapping/parse_rows с characteristics_col (сырьё в ParsedRow); import_parsed пишет `characteristics_raw`, при изменении raw сбрасывает characteristics в None; extract_batch берёт raw как источник; `GET /catalog/facets` агрегирует ключи→значения; `search_items(facets=...)` фильтрует (SQLite — обязательно зелёный); `GET /catalog/items?f=K=V` фильтрует.
- **Frontend:** ColumnMapper рендерит селектор характеристик; CatalogPage показывает фасет-фильтры из мок-ответа, выбор шлёт `f=` в запрос items.
- Сборка/линт/ruff чисто; миграция (add column) на боевом Postgres при деплое.

## Отложено

- Категорийные словари признаков (сейчас свободные ключи).
- Диапазонные фильтры (числовые), мультивыбор значений.
- Полная опечатко-устойчивость поиска (pg_trgm).
