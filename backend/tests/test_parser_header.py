from app.catalog.parser import detect_header_row, extract_columns, load_tables
from tests.catalog_files import make_bolid_xlsx, make_optimus_xlsx


def test_header_first_row():
    rows = load_tables(make_bolid_xlsx(), "b.xlsx")["Болид"]
    assert detect_header_row(rows) == 0


def test_header_after_garbage():
    rows = load_tables(make_optimus_xlsx(), "o.xlsx")["IP камеры"]
    assert detect_header_row(rows) == 2


def test_header_empty_sheet():
    assert detect_header_row([]) == 0
    assert detect_header_row([[None, None]]) == 0


def test_extract_columns_with_samples():
    rows = load_tables(make_bolid_xlsx(), "b.xlsx")["Болид"]
    cols = extract_columns(rows, header_row=0, sample_count=2)
    assert cols[0].index == 0
    assert cols[0].header == "Название"
    assert cols[0].samples == ["Сириус", "С2000-М"]
    assert cols[3].header == "Розничная_цена"
    assert cols[3].samples == ["36159.53", "12721.31"]
