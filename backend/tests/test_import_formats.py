from decimal import Decimal

from sqlalchemy import select

from app.catalog import detect
from app.catalog.importer import import_parsed, parse_rows
from app.catalog.models import CatalogItem, PriceLevel, Supplier
from app.catalog.schemas import ColumnMapping
from tests.fixtures import pricelists as P
from tests.orghelpers import get_or_create_org as _get_or_create_org


def _mapping_from_layout(layout, level_ids):
    """ColumnMapping из detected: ценовые колонки по порядку → переданные уровни."""
    price_cols = {level_ids[i]: pc.index for i, pc in enumerate(layout.price_columns)
                  if i < len(level_ids)}
    on_req = [pc.index for pc in layout.price_columns if pc.on_request]
    return ColumnMapping(
        name_col=layout.name_col, article_col=layout.article_col,
        unit_col=layout.unit_col, characteristics_col=layout.chars_col,
        manufacturer_col=layout.manufacturer_col, header_row=layout.header_row,
        data_start_row=layout.data_start_row, price_cols=price_cols,
        on_request_cols=on_req,
    )


def _setup(db, n_levels=3):
    org = _get_or_create_org(db)
    sup = Supplier(name="S", org_id=org.id); db.add(sup); db.commit()
    levels = [PriceLevel(name=f"L{i}", sort_order=i, org_id=org.id) for i in range(n_levels)]
    db.add_all(levels); db.commit()
    return sup, [lvl.id for lvl in levels], org


def _run(db, rows, n_levels=3):
    sup, lids, org = _setup(db, n_levels)
    layout = detect.detect_layout(rows)
    assert layout is not None
    parsed = parse_rows(rows, _mapping_from_layout(layout, lids))
    import_parsed(db, sup.id, "p.xlsx", parsed, kind="material", org_id=org.id)
    return db.scalars(select(CatalogItem).order_by(CatalogItem.id)).all()


def test_e2e_bolid(db_session):
    items = _run(db_session, P.BOLID, n_levels=2)
    assert {i.name for i in items} == {"Сириус", "С2000-М"}
    assert all(not i.price_on_request for i in items)


def test_e2e_kontrol_categories_and_zvonite(db_session):
    items = _run(db_session, P.KONTROL)
    assert {i.name for i in items} == {"CNC-02-IP", "NMI-08"}
    assert all(i.category == "Интегрированная система" for i in items)
    assert all(i.price_on_request for i in items)


def test_e2e_pricetin_unit_and_manufacturer(db_session):
    items = _run(db_session, P.PRICETIN)
    by_name = {i.name: i for i in items}
    assert by_name["DD-01"].unit == "шт"
    assert by_name["DD-01"].manufacturer == "CARDDEX"
    assert by_name["DD-01"].category == "Извещатели охранные"


def test_e2e_optimus_net_no_corruption(db_session):
    """Сдвинутый лист: характеристики НЕ содержат цену (главный баг старого импорта)."""
    items = _run(db_session, P.OPTIMUS_NET)
    item = items[0]
    assert item.name == "Коммутатор U1IC"
    assert item.characteristics_raw == "8 портов"
    assert not item.price_on_request


def test_e2e_akkum_on_request(db_session):
    items = _run(db_session, P.AKKUM, n_levels=5)
    assert items[0].price_on_request is True
