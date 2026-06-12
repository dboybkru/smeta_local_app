"""Чтение прайс-файлов: xlsx (openpyxl) и csv (auto-кодировка, auto-разделитель)."""

import csv
import io

from openpyxl import load_workbook

Cell = str | float | int | None
Rows = list[list[Cell]]


class UnsupportedFileError(Exception):
    pass


def load_tables(content: bytes, filename: str) -> dict[str, Rows]:
    """Файл -> {имя листа: строки}. Для csv единственный 'лист' с именем 'csv'."""
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return _load_xlsx(content)
    if lower.endswith(".csv"):
        return {"csv": _load_csv(content)}
    raise UnsupportedFileError(filename)


def _load_xlsx(content: bytes) -> dict[str, Rows]:
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    tables: dict[str, Rows] = {}
    for ws in wb.worksheets:
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
        tables[ws.title] = rows
    wb.close()
    return tables


def _load_csv(content: bytes) -> Rows:
    text = _decode(content)
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(row) for row in reader]


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")
