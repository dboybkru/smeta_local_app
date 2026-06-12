"""Смоук на реальных прайсах с машины разработчика. В CI скипается."""

from pathlib import Path

import pytest

from app.catalog.parser import detect_header_row, extract_columns, load_tables

REAL_DIR = Path("D:/git/прайсы")

requires_real_files = pytest.mark.skipif(
    not REAL_DIR.exists(), reason="реальные прайсы доступны только локально"
)


@requires_real_files
def test_bolid_real_file_parses():
    content = (REAL_DIR / "bolid_price.xlsx").read_bytes()
    tables = load_tables(content, "bolid_price.xlsx")
    rows = next(iter(tables.values()))
    header = detect_header_row(rows)
    columns = extract_columns(rows, header)
    headers = [c.header for c in columns]
    assert "Название" in headers
    assert any("цена" in h.lower() for h in headers)
    assert len(rows) > 100


@requires_real_files
def test_works_real_file_parses():
    content = (REAL_DIR / "работы.xlsx").read_bytes()
    tables = load_tables(content, "работы.xlsx")
    rows = next(iter(tables.values()))
    columns = extract_columns(rows, detect_header_row(rows))
    assert columns[0].header == "Наименование работы"


@requires_real_files
def test_optimus_real_file_lists_sheets():
    files = list(REAL_DIR.glob("Price_Optimus*.xlsx"))
    if not files:
        pytest.skip("прайс Optimus не найден")
    tables = load_tables(files[0].read_bytes(), files[0].name)
    assert len(tables) > 5  # многолистовой
