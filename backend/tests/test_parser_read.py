from app.catalog.parser import load_tables
from tests.catalog_files import make_bolid_csv, make_bolid_xlsx, make_optimus_xlsx


def test_xlsx_single_sheet():
    tables = load_tables(make_bolid_xlsx(), "bolid.xlsx")
    assert list(tables.keys()) == ["Болид"]
    rows = tables["Болид"]
    assert rows[0][0] == "Название"
    assert rows[1][0] == "Сириус"
    assert len(rows) == 4


def test_xlsx_multi_sheet():
    tables = load_tables(make_optimus_xlsx(), "optimus.xlsx")
    assert list(tables.keys()) == ["IP камеры", "Сетевое оборудование"]
    assert tables["IP камеры"][3][0] == "IP-E012.1"


def test_csv_semicolon_cp1251():
    tables = load_tables(make_bolid_csv(), "bolid.csv")
    assert list(tables.keys()) == ["csv"]
    rows = tables["csv"]
    assert rows[0] == ["Название", "Артикул", "Розничная_цена", "Оптовая_цена"]
    assert rows[1][0] == "Сириус"


def test_unsupported_extension():
    import pytest

    from app.catalog.parser import UnsupportedFileError

    with pytest.raises(UnsupportedFileError):
        load_tables(b"x", "file.pdf")
