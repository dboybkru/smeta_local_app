import json as json_lib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_active, require_admin
from app.catalog import importer, parser
from app.catalog.models import ItemPrice, PriceLevel, Supplier
from app.catalog.schemas import (
    ColumnMapping,
    ColumnOut,
    ImportSummaryOut,
    InspectOut,
    PriceLevelIn,
    PriceLevelOut,
    PriceLevelPatch,
    SheetOut,
    SupplierIn,
    SupplierOut,
)
from app.core.db import get_db

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


@router.get(
    "/price-levels", response_model=list[PriceLevelOut], dependencies=[Depends(require_active)]
)
def list_price_levels(db: Session = Depends(get_db)):
    return db.scalars(select(PriceLevel).order_by(PriceLevel.sort_order, PriceLevel.id)).all()


@router.post(
    "/price-levels",
    response_model=PriceLevelOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_price_level(body: PriceLevelIn, db: Session = Depends(get_db)):
    if db.scalar(select(PriceLevel).where(PriceLevel.name == body.name)):
        raise HTTPException(status_code=409, detail="Уровень с таким именем уже есть")
    level = PriceLevel(name=body.name, sort_order=body.sort_order)
    db.add(level)
    db.commit()
    db.refresh(level)
    return level


@router.patch(
    "/price-levels/{level_id}",
    response_model=PriceLevelOut,
    dependencies=[Depends(require_admin)],
)
def update_price_level(level_id: int, body: PriceLevelPatch, db: Session = Depends(get_db)):
    level = db.get(PriceLevel, level_id)
    if level is None:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    if body.name is not None and body.name != level.name:
        if db.scalar(select(PriceLevel).where(PriceLevel.name == body.name)):
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
def list_suppliers(db: Session = Depends(get_db)):
    return db.scalars(select(Supplier).order_by(Supplier.name)).all()


@router.post(
    "/suppliers", response_model=SupplierOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_supplier(body: SupplierIn, db: Session = Depends(get_db)):
    if db.scalar(select(Supplier).where(Supplier.name == body.name)):
        raise HTTPException(status_code=409, detail="Поставщик уже существует")
    supplier = Supplier(name=body.name)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete(
    "/price-levels/{level_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def delete_price_level(level_id: int, db: Session = Depends(get_db)):
    level = db.get(PriceLevel, level_id)
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
        sheets.append(
            SheetOut(name=name, row_count=len(rows), header_row=header_row, columns=columns)
        )
    return InspectOut(sheets=sheets)


@router.post(
    "/catalog/import", response_model=ImportSummaryOut, dependencies=[Depends(require_admin)]
)
async def import_file(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
    kind: str = Form(...),
    sheets: str = Form(...),
    mapping: str = Form(...),
    use_sheet_as_category: bool = Form(False),
    save_mapping: bool = Form(False),
    db: Session = Depends(get_db),
):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    if kind not in ("material", "work"):
        raise HTTPException(status_code=422, detail="kind: material или work")
    try:
        sheet_names = json_lib.loads(sheets)
        col_mapping = ColumnMapping.model_validate(json_lib.loads(mapping))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Невалидный JSON в sheets/mapping")

    tables = _load_tables_or_415(await _read_limited(file), file.filename or "")
    parsed: list[importer.ParsedRow] = []
    for sheet_name in sheet_names:
        if sheet_name not in tables:
            raise HTTPException(status_code=422, detail=f"Лист «{sheet_name}» не найден")
        rows = tables[sheet_name]
        header_row = parser.detect_header_row(rows)
        parsed.extend(
            importer.parse_rows(
                rows,
                header_row,
                col_mapping,
                default_category=sheet_name if use_sheet_as_category else "",
            )
        )

    try:
        summary = importer.import_parsed(
            db, supplier_id, file.filename or "import", parsed, kind=kind
        )
    except Exception:
        db.rollback()
        raise
    if save_mapping:
        supplier.column_mapping_template = col_mapping.model_dump()
        db.commit()
    return ImportSummaryOut(**summary.__dict__)
