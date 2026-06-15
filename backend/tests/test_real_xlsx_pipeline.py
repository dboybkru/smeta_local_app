"""Regression test against a committed real .xlsx binary (bolid_sample.xlsx).

The file is committed to the repo so this test runs in CI without any external paths.
It exercises the full load → detect → map → parse_rows pipeline.
"""

from decimal import Decimal
from pathlib import Path

from app.catalog.detect import detect_layout
from app.catalog.importer import parse_rows
from app.catalog.parser import load_tables
from app.catalog.schemas import ColumnMapping

FIXTURE = Path(__file__).parent / "fixtures" / "real" / "bolid_sample.xlsx"


def _load_rows():
    content = FIXTURE.read_bytes()
    tables = load_tables(content, "bolid_sample.xlsx")
    sheet_name = next(iter(tables))
    return tables[sheet_name]


def test_fixture_file_exists():
    """Binary fixture must be committed and readable."""
    assert FIXTURE.exists(), f"Файл-эталон не найден: {FIXTURE}"
    assert FIXTURE.stat().st_size > 1000


def test_detect_layout_finds_header():
    rows = _load_rows()
    layout = detect_layout(rows)
    assert layout is not None
    assert layout.header_row == 0  # шапка в первой строке
    assert layout.name_col is not None  # колонка «Название» найдена
    assert layout.article_col is not None  # колонка «Артикул» или «Код» найдена
    # Должно быть >=2 ценовых колонки (Розничная + Оптовая)
    assert len(layout.price_columns) >= 2


def test_parse_rows_correct_product_count():
    """После парсинга должно быть ровно столько продуктовых строк, сколько в файле."""
    rows = _load_rows()
    layout = detect_layout(rows)
    assert layout is not None

    # Маппинг: первые два price_column → dummy price level ids 1 и 2
    price_cols = {
        idx + 1: pc.index
        for idx, pc in enumerate(layout.price_columns[:2])
    }
    mapping = ColumnMapping(
        name_col=layout.name_col,
        article_col=layout.article_col,
        characteristics_col=layout.chars_col,
        header_row=layout.header_row,
        data_start_row=layout.data_start_row,
        price_cols=price_cols,
    )
    parsed = parse_rows(rows, mapping)

    # Файл содержит 5 строк данных; одна строка с пустой розничной ценой и
    # одна «звоните» — обе должны войти в результат (не отброшены)
    assert len(parsed) == 5, (
        f"Ожидалось 5 строк, получено {len(parsed)}: "
        + ", ".join(r.name for r in parsed)
    )


def test_parse_rows_name_and_article():
    """Имя и артикул первой строки распознаны корректно."""
    rows = _load_rows()
    layout = detect_layout(rows)
    assert layout is not None
    price_cols = {1: layout.price_columns[0].index} if layout.price_columns else {}
    mapping = ColumnMapping(
        name_col=layout.name_col,
        article_col=layout.article_col,
        header_row=layout.header_row,
        data_start_row=layout.data_start_row,
        price_cols=price_cols,
    )
    parsed = parse_rows(rows, mapping)
    first = parsed[0]
    assert "Сириус" in first.name
    assert first.article != ""


def test_parse_rows_on_request_row():
    """Строка с «звоните» получает price_on_request=True и цену 0."""
    rows = _load_rows()
    layout = detect_layout(rows)
    assert layout is not None
    price_cols = {
        idx + 1: pc.index
        for idx, pc in enumerate(layout.price_columns[:2])
    }
    mapping = ColumnMapping(
        name_col=layout.name_col,
        article_col=layout.article_col,
        header_row=layout.header_row,
        data_start_row=layout.data_start_row,
        price_cols=price_cols,
    )
    parsed = parse_rows(rows, mapping)

    on_req = [r for r in parsed if r.price_on_request]
    assert len(on_req) >= 1, "Строка «звоните» не распознана как price_on_request"
    for r in on_req:
        for val in r.prices.values():
            assert val == Decimal("0.00"), (
                f"Цена у price_on_request строки должна быть 0, получено {val}"
            )


def test_parse_rows_blank_price_row_handled():
    """Строка с пустой ценой в одной колонке не вызывает ошибок (partial price ok)."""
    rows = _load_rows()
    layout = detect_layout(rows)
    assert layout is not None
    price_cols = {
        idx + 1: pc.index
        for idx, pc in enumerate(layout.price_columns[:2])
    }
    mapping = ColumnMapping(
        name_col=layout.name_col,
        article_col=layout.article_col,
        header_row=layout.header_row,
        data_start_row=layout.data_start_row,
        price_cols=price_cols,
    )
    parsed = parse_rows(rows, mapping)

    # Строка «С2000-ИП» имеет пустую розничную цену, но ненулевую оптовую.
    # Парсер должен принять её (частичные цены допустимы) или пропустить с проблемой,
    # но НЕ упасть с исключением.
    ip_rows = [r for r in parsed if "С2000-ИП" in r.name]
    assert len(ip_rows) == 1, "Строка С2000-ИП должна присутствовать в результате"
    ip = ip_rows[0]
    # Должна быть хотя бы одна цена (оптовая)
    assert len(ip.prices) >= 1, "С2000-ИП: ожидается хотя бы одна ненулевая цена"


def test_characteristics_col_did_not_capture_price():
    """Anti-corruption: колонка «Описание» не должна содержать числовую цену."""
    rows = _load_rows()
    layout = detect_layout(rows)
    assert layout is not None
    # Проверяем, что chars_col != price_col (структурный тест)
    if layout.chars_col is not None:
        price_indices = {pc.index for pc in layout.price_columns}
        assert layout.chars_col not in price_indices, (
            f"chars_col={layout.chars_col} совпадает с одной из ценовых колонок: "
            f"{price_indices}"
        )

    price_cols = {
        idx + 1: pc.index
        for idx, pc in enumerate(layout.price_columns[:2])
    }
    mapping = ColumnMapping(
        name_col=layout.name_col,
        article_col=layout.article_col,
        characteristics_col=layout.chars_col,
        header_row=layout.header_row,
        data_start_row=layout.data_start_row,
        price_cols=price_cols,
    )
    parsed = parse_rows(rows, mapping)

    for row in parsed:
        if row.characteristics:
            # Описание не должно быть чисто числовым (т.е. не быть ценой)
            assert not row.characteristics.replace(".", "").replace(",", "").isdigit(), (
                f"characteristics у «{row.name}» выглядит как цена: «{row.characteristics}»"
            )
