import json as json_lib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth.deps import current_org, require_active, require_admin
from app.catalog import detect, importer, parser, service
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier
from app.catalog.schemas import (
    ColumnOut,
    DetectedLayoutOut,
    ImportSheetMapping,
    ImportSummaryOut,
    InspectOut,
    ItemOut,
    ItemsPageOut,
    PriceColumnOut,
    PriceHistoryOut,
    PriceLevelIn,
    PriceLevelOut,
    PriceLevelPatch,
    PriceListOut,
    SheetOut,
    SupplierIn,
    SupplierOut,
)
from app.core.db import get_db
from app.jobs.models import Job
from app.jobs.schemas import JobOut

router = APIRouter(prefix="/api", tags=["catalog"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # реальный прайс Optimus ~7 МБ


async def _read_limited(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 25 МБ")
    return content


def _load_tables_or_415(content: bytes, filename: str) -> dict:
    try:
        return parser.load_tables(content, filename)
    except parser.UnsupportedFileError:
        raise HTTPException(status_code=415, detail="Поддерживаются только .xlsx и .csv")
    except parser.CorruptFileError:
        raise HTTPException(status_code=422, detail="Файл повреждён или не является xlsx")


@router.get(
    "/price-levels", response_model=list[PriceLevelOut], dependencies=[Depends(require_active)]
)
def list_price_levels(
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(PriceLevel)
        .where(PriceLevel.org_id == org)
        .order_by(PriceLevel.sort_order, PriceLevel.id)
    ).all()


@router.post(
    "/price-levels",
    response_model=PriceLevelOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_price_level(
    body: PriceLevelIn,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    if db.scalar(
        select(PriceLevel).where(PriceLevel.org_id == org, PriceLevel.name == body.name)
    ):
        raise HTTPException(status_code=409, detail="Уровень с таким именем уже есть")
    level = PriceLevel(name=body.name, sort_order=body.sort_order, org_id=org)
    db.add(level)
    db.commit()
    db.refresh(level)
    return level


@router.patch(
    "/price-levels/{level_id}",
    response_model=PriceLevelOut,
    dependencies=[Depends(require_admin)],
)
def update_price_level(
    level_id: int,
    body: PriceLevelPatch,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    level = db.scalar(
        select(PriceLevel).where(PriceLevel.id == level_id, PriceLevel.org_id == org)
    )
    if level is None:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    if body.name is not None and body.name != level.name:
        if db.scalar(
            select(PriceLevel).where(PriceLevel.org_id == org, PriceLevel.name == body.name)
        ):
            raise HTTPException(status_code=409, detail="Уровень с таким именем уже есть")
        level.name = body.name
    if body.sort_order is not None:
        level.sort_order = body.sort_order
    db.commit()
    db.refresh(level)
    return level


@router.get(
    "/suppliers", response_model=list[SupplierOut], dependencies=[Depends(require_active)]
)
def list_suppliers(
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Supplier).where(Supplier.org_id == org).order_by(Supplier.name)
    ).all()


@router.post(
    "/suppliers", response_model=SupplierOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_supplier(
    body: SupplierIn,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    if db.scalar(
        select(Supplier).where(Supplier.org_id == org, Supplier.name == body.name)
    ):
        raise HTTPException(status_code=409, detail="Поставщик уже существует")
    supplier = Supplier(name=body.name, org_id=org)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete(
    "/price-levels/{level_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def delete_price_level(
    level_id: int,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    level = db.scalar(
        select(PriceLevel).where(PriceLevel.id == level_id, PriceLevel.org_id == org)
    )
    if level is None:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    if db.scalar(select(ItemPrice).where(ItemPrice.price_level_id == level_id).limit(1)):
        raise HTTPException(
            status_code=409, detail="Уровень используется в ценах — удалить нельзя"
        )
    db.delete(level)
    db.commit()


@router.post("/catalog/inspect", response_model=InspectOut, dependencies=[Depends(require_admin)])
async def inspect_file(file: UploadFile = File(...)):
    tables = _load_tables_or_415(await _read_limited(file), file.filename or "")
    sheets = []
    for name, rows in tables.items():
        header_row = parser.detect_header_row(rows)
        columns = [
            ColumnOut(index=c.index, header=c.header, samples=c.samples)
            for c in parser.extract_columns(rows, header_row)
        ]
        layout = detect.detect_layout(rows)
        detected = None
        if layout is not None:
            detected = DetectedLayoutOut(
                header_row=layout.header_row,
                data_start_row=layout.data_start_row,
                name_col=layout.name_col,
                article_col=layout.article_col,
                chars_col=layout.chars_col,
                unit_col=layout.unit_col,
                manufacturer_col=layout.manufacturer_col,
                price_columns=[
                    PriceColumnOut(index=p.index, label=p.label, sample=p.sample,
                                   on_request=p.on_request)
                    for p in layout.price_columns
                ],
                confidence=layout.confidence,
            )
        sheets.append(
            SheetOut(name=name, row_count=len(rows), header_row=header_row,
                     columns=columns, detected=detected)
        )
    return InspectOut(sheets=sheets)


@router.post(
    "/catalog/import", response_model=ImportSummaryOut, dependencies=[Depends(require_admin)]
)
async def import_file(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
    kind: str = Form(...),
    sheet_mappings: str = Form(...),
    use_sheet_as_category: bool = Form(False),
    save_mapping: bool = Form(False),
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    # Verify supplier belongs to this org
    supplier = db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.org_id == org)
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    if kind not in ("material", "work"):
        raise HTTPException(status_code=422, detail="kind: material или work")
    try:
        items = [ImportSheetMapping.model_validate(x) for x in json_lib.loads(sheet_mappings)]
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Невалидный JSON в sheet_mappings")
    if not items:
        raise HTTPException(status_code=422, detail="Не выбран ни один лист")

    # Проверяем, что все price_level_id из маппинга принадлежат текущей организации
    referenced_level_ids: set[int] = set()
    for sm in items:
        referenced_level_ids.update(sm.mapping.price_cols.keys())
    if referenced_level_ids:
        own_level_ids = set(
            db.scalars(
                select(PriceLevel.id).where(PriceLevel.org_id == org)
            ).all()
        )
        alien_ids = referenced_level_ids - own_level_ids
        if alien_ids:
            raise HTTPException(
                status_code=422,
                detail="Уровень цены не принадлежит вашей организации",
            )

    tables = _load_tables_or_415(await _read_limited(file), file.filename or "")
    parsed: list[importer.ParsedRow] = []
    for sm in items:
        if sm.name not in tables:
            raise HTTPException(status_code=422, detail=f"Лист «{sm.name}» не найден")
        parsed.extend(
            importer.parse_rows(
                tables[sm.name],
                sm.mapping,
                default_category=sm.name if use_sheet_as_category else "",
            )
        )

    try:
        summary = importer.import_parsed(
            db, supplier_id, file.filename or "import", parsed, kind=kind, org_id=org
        )
    except Exception:
        db.rollback()
        raise
    if save_mapping and items:
        supplier.column_mapping_template = items[0].mapping.model_dump()
        db.commit()
    return ImportSummaryOut(**summary.__dict__)


@router.get(
    "/catalog/items", response_model=ItemsPageOut, dependencies=[Depends(require_active)]
)
def list_items(
    q: str = "",
    supplier_id: int | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
    f: list[str] = Query(default=[]),
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    facets = {}
    for pair in f:
        if "=" in pair:
            k, v = pair.split("=", 1)
            facets[k] = v
    items, total = service.search_items(
        db, q, supplier_id, kind, min(limit, 200), offset, facets=facets, org_id=org
    )
    prices = service.latest_prices_for(db, [i.id for i in items])
    out = [
        ItemOut(
            id=i.id,
            supplier_id=i.supplier_id,
            name=i.name,
            article=i.article,
            unit=i.unit,
            category=i.category,
            kind=i.kind,
            manufacturer=i.manufacturer,
            price_on_request=i.price_on_request,
            prices=prices.get(i.id, {}),
            characteristics=i.characteristics,
        )
        for i in items
    ]
    return ItemsPageOut(items=out, total=total)


@router.get("/catalog/facets", dependencies=[Depends(require_active)])
def catalog_facets(
    supplier_id: int | None = None,
    kind: str | None = None,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    query = select(CatalogItem.characteristics).where(
        CatalogItem.characteristics.isnot(None),
        CatalogItem.org_id == org,
    )
    if supplier_id is not None:
        query = query.where(CatalogItem.supplier_id == supplier_id)
    if kind is not None:
        query = query.where(CatalogItem.kind == kind)
    facets: dict[str, set] = {}
    for (chars,) in db.execute(query.limit(2000)).all():
        if not isinstance(chars, dict):
            continue
        for k, v in chars.items():
            if v:
                facets.setdefault(str(k), set()).add(str(v))
    return {k: sorted(vs)[:50] for k, vs in list(facets.items())[:40]}


@router.get(
    "/catalog/items/{item_id}/prices",
    response_model=list[PriceHistoryOut],
    dependencies=[Depends(require_active)],
)
def item_price_history(
    item_id: int,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    item = db.scalar(
        select(CatalogItem).where(CatalogItem.id == item_id, CatalogItem.org_id == org)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    rows = db.execute(
        select(ItemPrice, PriceList)
        .join(PriceList, PriceList.id == ItemPrice.price_list_id)
        .where(ItemPrice.item_id == item_id)
        .order_by(PriceList.version.desc())
    ).all()
    return [
        PriceHistoryOut(
            price_list_id=price.price_list_id,
            version=price_list.version,
            imported_at=price_list.imported_at.isoformat(),
            price_level_id=price.price_level_id,
            value=price.value,
        )
        for price, price_list in rows
    ]


@router.get(
    "/catalog/price-lists",
    response_model=list[PriceListOut],
    dependencies=[Depends(require_active)],
)
def list_price_lists(
    supplier_id: int | None = None,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    query = select(PriceList).where(PriceList.org_id == org).order_by(PriceList.imported_at.desc())
    if supplier_id is not None:
        query = query.where(PriceList.supplier_id == supplier_id)
    rows = db.scalars(query).all()
    return [
        PriceListOut(
            id=pl.id,
            supplier_id=pl.supplier_id,
            filename=pl.filename,
            version=pl.version,
            imported_at=pl.imported_at.isoformat() if pl.imported_at else None,
        )
        for pl in rows
    ]


@router.post(
    "/catalog/extract-characteristics/start",
    response_model=JobOut,
    dependencies=[Depends(require_admin)],
)
def start_extract_characteristics(
    supplier_id: int | None = None,
    force: bool = False,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    """Запускает извлечение характеристик фоновой задачей. Если активная задача уже
    есть — возвращает её (без дублирования расхода). force=true — сбросить уже
    извлечённые характеристики (в т.ч. пустые {}) и переизвлечь заново."""
    active = db.scalars(
        select(Job).where(
            Job.type == "catalog_extract",
            Job.status.in_(("pending", "running")),
            Job.org_id == org,
        )
    ).first()
    if active is not None:
        return active
    if force:
        q = update(CatalogItem).values(characteristics=None).where(CatalogItem.org_id == org)
        if supplier_id is not None:
            q = q.where(CatalogItem.supplier_id == supplier_id)
        db.execute(q)
        db.commit()
    job = Job(type="catalog_extract", org_id=org,
              params={"supplier_id": supplier_id, "org_id": org})
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/catalog/items", dependencies=[Depends(require_admin)])
def clear_catalog(
    supplier_id: int | None = None,
    org: int = Depends(current_org),
    db: Session = Depends(get_db),
):
    """Очистка каталога (опц. по поставщику): удаляет позиции и их цены, отвязывает
    строки смет (item_id→NULL, снапшоты сумм в сметах сохраняются).
    Scope: только позиции текущей org."""
    from app.estimates.models import EstimateLine

    q = select(CatalogItem.id).where(CatalogItem.org_id == org)
    if supplier_id is not None:
        q = q.where(CatalogItem.supplier_id == supplier_id)
    ids = list(db.scalars(q).all())
    if ids:
        db.execute(update(EstimateLine).where(EstimateLine.item_id.in_(ids)).values(item_id=None))
        db.execute(delete(ItemPrice).where(ItemPrice.item_id.in_(ids)))
        db.execute(delete(CatalogItem).where(CatalogItem.id.in_(ids)))
        db.commit()
    return {"deleted": len(ids)}
