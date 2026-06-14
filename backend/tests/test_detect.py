from app.catalog.detect import detect_layout
from tests.fixtures import pricelists as P


def test_detect_bolid_flat():
    d = detect_layout(P.BOLID)
    assert d is not None
    assert d.header_row == 0
    assert d.data_start_row == 1
    assert d.name_col == 0
    assert d.chars_col == 1
    assert d.article_col == 3
    labels = {p.index for p in d.price_columns}
    assert labels == {5, 6}


def test_detect_raboty():
    d = detect_layout(P.RABOTY)
    assert d.header_row == 0
    assert d.name_col == 0
    assert d.unit_col == 2
    assert [p.index for p in d.price_columns] == [1]


def test_detect_optimus_ipk_header_row_6_with_spacer():
    d = detect_layout(P.OPTIMUS_IPK)
    assert d.header_row == 5
    assert d.data_start_row == 6
    assert d.name_col == 0
    assert d.chars_col == 3
    assert d.article_col == 10
    assert [p.index for p in d.price_columns] == [4, 5, 6, 7, 8]


def test_detect_optimus_net_shifted():
    d = detect_layout(P.OPTIMUS_NET)
    assert d.header_row == 5
    assert d.chars_col == 2
    assert [p.index for p in d.price_columns] == [3, 4, 5, 6, 7]
