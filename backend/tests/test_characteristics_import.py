from app.catalog import importer
from app.catalog.models import CatalogItem, Supplier
from app.catalog.schemas import ColumnMapping


def _rows():
    return [
        ["Наименование", "Артикул", "Характеристики"],
        ["Камера X", "A1", "2 Мп, объектив 2.8мм, IP67"],
    ]


def test_parse_rows_reads_characteristics_col():
    m = ColumnMapping(name_col=0, article_col=1, characteristics_col=2)
    parsed = importer.parse_rows(_rows(), 0, m)
    assert parsed[0].characteristics == "2 Мп, объектив 2.8мм, IP67"


def test_import_stores_raw_and_resets_on_change(db_session):
    sup = Supplier(name="S"); db_session.add(sup); db_session.commit()
    m = ColumnMapping(name_col=0, article_col=1, characteristics_col=2)
    parsed = importer.parse_rows(_rows(), 0, m)
    importer.import_parsed(db_session, sup.id, "f.xlsx", parsed, kind="material")
    it = db_session.scalars(__import__("sqlalchemy").select(CatalogItem)).first()
    assert it.characteristics_raw == "2 Мп, объектив 2.8мм, IP67"
    # имитируем уже извлечённые признаки
    it.characteristics = {"Разрешение": "2 Мп"}; db_session.commit()
    # повторный импорт с ИЗМЕНЁННЫМ сырьём → characteristics сбрасывается в None
    rows2 = [["Наименование", "Артикул", "Характеристики"], ["Камера X", "A1", "4 Мп, IP66"]]
    importer.import_parsed(db_session, sup.id, "f2.xlsx", importer.parse_rows(rows2, 0, m), kind="material")
    db_session.refresh(it)
    assert it.characteristics_raw == "4 Мп, IP66"
    assert it.characteristics is None
