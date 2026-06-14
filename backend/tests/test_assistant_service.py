from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.assistant import schemas


def test_operation_union_discriminates_by_op():
    adapter = TypeAdapter(schemas.Operation)
    add = adapter.validate_python({"op": "add_section", "name": "Оборудование"})
    assert isinstance(add, schemas.AddSection)
    line = adapter.validate_python(
        {"op": "add_catalog_line", "section_name": "Оборудование", "catalog_item_id": 5, "qty": "2"}
    )
    assert isinstance(line, schemas.AddCatalogLine)
    assert line.qty == Decimal("2")
    with pytest.raises(ValidationError):
        adapter.validate_python({"op": "nope"})
