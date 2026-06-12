# Фаза 3 — Редактор смет: дизайн

> Уточняющий спек к общему дизайн-доку `2026-06-11-smeta-app-design.md` (секция 6). Фиксирует рамки MVP фазы 3 и денежную логику. Дизайн одобрен пользователем 2026-06-12.

## Рамки фазы 3

**Разбивка:** 3a — бэкенд смет (эта итерация по бэкенду), 3b — фронтенд редактора (следующая). Как в фазе 2 (2a/2b).

**Ядро MVP:** создать смету → разделы → строки из каталога (со снапшотом цены) или произвольные → расчёт итогов (материалы/работы/всего, наценка по разделу, НДС) → маржа для владельца.

**Отложено (в конец фазы 3 / фазу 3.5, без миграций схемы):**
- Ветки-варианты (эконом/стандарт/премиум) и сравнение веток — сущность `EstimateBranch` остаётся, но создаётся ровно одна «Базовая» ветка на смету; UI/логика вариантов не делается.
- Автоподбор работ (`WorkRule` + админка правил).
- Отдельная страница CRUD клиентов — на старте клиент создаётся инлайн при создании сметы.

Экспорт/публичные ссылки — фаза 4, AI-ассистент — фаза 5 (не входят).

## Модель данных (фаза 3a)

Numeric/Decimal везде, никаких float. Модуль `backend/app/estimates/`.

```
Client          id, name, default_price_level_id? (FK→PriceLevel), created_at
Estimate        id, client_id (FK→Client), owner_id (FK→User), object_name,
                status (draft|sent|approved|archived, default draft),
                vat_enabled (bool, default false), vat_rate (Numeric(5,2), default 20),
                created_at
EstimateBranch  id, estimate_id (FK), parent_branch_id? (FK→self), name (default "Базовая")
EstimateSection id, branch_id (FK), name, sort_order (int), markup_percent (Numeric(5,2), default 0)
EstimateLine    id, section_id (FK), item_id? (FK→CatalogItem), name, unit,
                qty (Numeric(12,3)), work_price (Numeric(12,2), default 0),
                material_price (Numeric(12,2), default 0),
                purchase_price_snapshot? (Numeric(12,2)), sort_order (int)
```

- `tax_mode` из общего дизайн-дока реализуется как пара `vat_enabled` + `vat_rate` (НДС вкл/выкл, ставка настраиваемая, по умолчанию 20%).
- `EstimateBranch` сохранён как отдельная сущность (разделы привязаны к `branch_id`, не к `estimate_id`), чтобы варианты потом легли без миграции. Создаётся одна базовая ветка на смету.
- Каскадное удаление: удаление сметы → ветки → разделы → строки.

## Снапшот цен и уровень «Закупка»

При добавлении позиции **из каталога** (`item_id` задан):
- Продажная цена снимается с `ItemPrice` по уровню клиента (`client.default_price_level_id`; если у клиента не задан — первый уровень по `sort_order`) и кладётся в `material_price` или `work_price` в зависимости от `CatalogItem.kind` (material/work); вторая цена = 0.
- Закупочная цена снимается с `ItemPrice` по уровню с именем **«Закупка»** (точное совпадение `PriceLevel.name == "Закупка"`) → `purchase_price_snapshot`. Если уровня «Закупка» нет или у позиции нет такой цены — `purchase_price_snapshot = null` (маржа по строке не считается).
- Цены берутся из **последней версии** прайса поставщика (используется уже готовый `service.latest_prices_for` из каталога) и **фиксируются** в строке. Последующий импорт прайса не меняет существующие строки смет.
- `name`, `unit` копируются из позиции каталога (можно переопределить вручную).

**Произвольная строка** (`item_id = null`): `name`/`unit`/`qty`/цены вводятся вручную; `purchase_price_snapshot` опционально.

**Ручное переопределение:** любая цена строки (`work_price`, `material_price`) и `qty` редактируются через `PATCH /lines/{id}`; снапшот закупки при этом не трогается, если не передан явно.

## Расчёт итогов (TDD, денежная логика)

Все суммы — `Decimal`, округление до копеек (`quantize(0.01)`) на границах вывода.

- **Строка:** `line_total = (work_price + material_price) * qty`. Разделяем материалы/работы: `line_materials = material_price * qty`, `line_works = work_price * qty`.
- **Раздел:** `sect_materials = Σ line_materials`, `sect_works = Σ line_works`, `sect_base = sect_materials + sect_works`; наценка раздела: `sect_total = sect_base * (1 + markup_percent/100)`. Наценка применяется к продажной сумме раздела (поверх цен уровня клиента).
- **Смета (до НДС):** `subtotal = Σ sect_total` (а также раздельно materials/works для строки «в т.ч.»).
- **НДС:** если `vat_enabled` → `vat = subtotal * vat_rate/100`, `total = subtotal + vat`; иначе `vat = 0`, `total = subtotal`.
- **Закупка по разделу:** `sect_purchase = Σ (purchase_price_snapshot * qty)` по строкам, где снапшот не null.
- **Маржа (только owner/admin)** считается на уровне раздела и сметы (не размазывается по строкам, чтобы избежать неоднозначного распределения наценки): `sect_margin = sect_total - sect_purchase` (продажная сумма раздела с наценкой минус закупка); `estimate_margin = Σ sect_margin`. В строке отдаются `purchase_price_snapshot` и продажные цены (owner/admin), но «маржа» как число — атрибут раздела/сметы. Если у всех строк раздела нет снапшота, `sect_purchase = 0` и маржа = `sect_total` (помечается как неполная — нет данных о закупке).

Итоги считаются на бэкенде в `service.py` и возвращаются в ответе `GET /estimates/{id}` (по разделам и по смете).

## API

Префикс `/api`. Все маршруты под `require_active`. Доступ к смете: `estimator` — только свои (`owner_id == current_user`), `admin` — все, `viewer` — чтение (своих/назначенных — на старте: чтение всех, write запрещён).

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/clients` | список клиентов |
| POST | `/clients` | создать клиента `{name, default_price_level_id?}` |
| GET | `/estimates` | список смет (свои/все по роли) |
| POST | `/estimates` | создать `{client_id?, object_name, vat_enabled?, vat_rate?}` → авто-создаётся «Базовая» ветка |
| GET | `/estimates/{id}` | полная смета: ветки→разделы→строки + итоги + маржа (по роли) |
| PATCH | `/estimates/{id}` | `{object_name?, status?, vat_enabled?, vat_rate?, client_id?}` |
| DELETE | `/estimates/{id}` | удалить смету (каскад) |
| POST | `/estimates/{id}/sections` | добавить раздел `{name, markup_percent?}` (в базовую ветку) |
| PATCH | `/sections/{id}` | `{name?, sort_order?, markup_percent?}` |
| DELETE | `/sections/{id}` | удалить раздел (каскад строк) |
| POST | `/sections/{id}/lines` | добавить строку: из каталога `{item_id, qty}` (снапшот цен) или произвольную `{name, unit, qty, work_price?, material_price?}` |
| PATCH | `/lines/{id}` | `{qty?, work_price?, material_price?, name?, unit?, sort_order?}` |
| DELETE | `/lines/{id}` | удалить строку |

Маржа и `purchase_price_snapshot` в ответах присутствуют только для владельца сметы и admin; для прочих эти поля опускаются/занулены.

## Тестирование (TDD)

Денежная логика — тесты до кода:
- Снапшот при добавлении позиции из каталога (продажная по уровню клиента, закупка по уровню «Закупка», fallback при отсутствии уровней).
- Расчёт строки/раздела/сметы; наценка раздела; НДС вкл/выкл с разными ставками; раздельные итоги материалы/работы.
- Маржа: расчёт, учёт наценки, сокрытие по роли (viewer/не-владелец не видит).
- Доступ: estimator не видит чужие сметы (404/403); admin видит все.
- Каскадное удаление.
- Сверка итогов хотя бы по **одной реальной смете-эталону** пользователя (`D:\Yandex.Disk\ИП\2026\…`) — фикстура с ожидаемой суммой.

## Решения (зафиксировано)

1. `markup_percent` — наценка сверху на продажную сумму раздела (поверх цен уровня клиента); маржа считается отдельно через `purchase_price_snapshot`.
2. `viewer` и не-владелец не получают поля маржи/закупки.
3. `EstimateBranch` остаётся в схеме (одна базовая ветка), варианты — позже без миграции.
4. Клиент создаётся инлайн; отдельная страница клиентов — позже.
5. НДС — `vat_enabled` + настраиваемая `vat_rate` (по умолчанию 20%, выключен по умолчанию).
6. Закупка — отдельный ценовой уровень «Закупка» в каталоге; снапшот при добавлении.
