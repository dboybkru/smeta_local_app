from decimal import Decimal

from sqlalchemy import select

from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier
from app.estimates.models import Client
from app.estimates.service import snapshot_line_values
from app.orgs.models import Organization


def _get_org(db):
    org = db.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db.add(org)
        db.commit()
    return org


def _catalog(db, kind="material", prices=None):
    """prices: {level_name: value}. Создаёт поставщика, позицию, уровни, прайс-лист, цены."""
    org = _get_org(db)
    sup = Supplier(name="Поставщик", org_id=org.id)
    db.add(sup)
    db.commit()
    item = CatalogItem(
        supplier_id=sup.id, name="Камера", article="A1", unit="шт", kind=kind, org_id=org.id
    )
    db.add(item)
    pl = PriceList(supplier_id=sup.id, filename="p.xlsx", version=1, org_id=org.id)
    db.add(pl)
    db.commit()
    levels = {}
    for i, (lname, value) in enumerate((prices or {}).items()):
        lvl = PriceLevel(name=lname, sort_order=i, org_id=org.id)
        db.add(lvl)
        db.commit()
        levels[lname] = lvl
        db.add(
            ItemPrice(
                item_id=item.id,
                price_list_id=pl.id,
                price_level_id=lvl.id,
                value=Decimal(value),
            )
        )
    db.commit()
    return item, levels


def test_material_snapshot_uses_client_level_and_zakupka(db_session):
    item, levels = _catalog(
        db_session, kind="material", prices={"Закупка": "100.00", "Розница": "150.00"}
    )
    org = _get_org(db_session)
    client = Client(name="C", org_id=org.id, default_price_level_id=levels["Розница"].id)
    db_session.add(client)
    db_session.commit()
    work, material, purchase = snapshot_line_values(db_session, item, client)
    assert material == Decimal("150.00")
    assert work == Decimal("0")
    assert purchase == Decimal("100.00")


def test_work_kind_fills_work_price(db_session):
    item, levels = _catalog(db_session, kind="work", prices={"Розница": "500.00"})
    org = _get_org(db_session)
    client = Client(name="C", org_id=org.id, default_price_level_id=levels["Розница"].id)
    db_session.add(client)
    db_session.commit()
    work, material, purchase = snapshot_line_values(db_session, item, client)
    assert work == Decimal("500.00")
    assert material == Decimal("0")
    assert purchase is None  # нет уровня «Закупка»


def test_no_client_uses_first_level_by_sort_order(db_session):
    item, levels = _catalog(
        db_session, kind="material", prices={"Розница": "150.00", "Опт": "120.00"}
    )
    # Розница sort_order=0 (добавлена первой) → используется когда client=None
    work, material, purchase = snapshot_line_values(db_session, item, None)
    assert material == Decimal("150.00")
