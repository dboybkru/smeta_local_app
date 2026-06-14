from app.catalog.schemas import ColumnMapping, DetectedLayoutOut, ImportSheetMapping


def test_column_mapping_new_fields_optional():
    m = ColumnMapping(name_col=0)
    assert m.manufacturer_col is None
    assert m.header_row == 0
    assert m.data_start_row is None
    assert m.on_request_cols == []


def test_detected_layout_out_roundtrip():
    d = DetectedLayoutOut(
        header_row=1, data_start_row=3, name_col=2,
        price_columns=[{"index": 4, "label": "Цена 1", "sample": "100",
                        "on_request": False}],
    )
    assert d.price_columns[0].index == 4


def test_import_sheet_mapping():
    s = ImportSheetMapping(name="Лист1", mapping=ColumnMapping(name_col=0))
    assert s.name == "Лист1"
