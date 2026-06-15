#!/usr/bin/env python
"""One-off generator — run once to produce bolid_sample.xlsx binary committed to repo."""

from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).parent


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Прайс"

    # Header row (row 1, index 0 in 0-based terms → Excel row 1)
    header = ["Название", "Описание", "Код", "Артикул", "Наличие",
              "Розничная_цена", "Оптовая_цена", "URL"]
    ws.append(header)

    # 5 data rows:
    # 1. Normal camera row with two prices
    ws.append([
        "Сириус-ВК-П-3-15 (2.8-12)",
        "Видеокамера 3 Мп, вариофокальный объектив 2.8-12 мм",
        "303232",
        "1-520-887-052",
        "В наличии",
        "36159.53",
        "33378.03",
        "https://bolid.ru/production/cameras/",
    ])

    # 2. DVR row with two prices
    ws.append([
        "С2000-М",
        "Пульт контроля и управления охраной",
        "004432",
        "110-058-274",
        "В наличии",
        "12721.31",
        "11742.74",
        "https://bolid.ru/production/c2000-m/",
    ])

    # 3. Row with "звоните" price (price_on_request)
    ws.append([
        "Орион Про 1.21 (Модуль АРМ)",
        "Программное обеспечение, лицензия на 1 рабочее место",
        "099910",
        "SW-001-PRO",
        "Под заказ",
        "звоните",
        "звоните",
        "https://bolid.ru/production/orion/",
    ])

    # 4. Row with blank retail price (only wholesale price)
    ws.append([
        "С2000-ИП",
        "Извещатель пожарный тепловой",
        "024401",
        "IP-TH-1",
        "В наличии",
        "",
        "1890.00",
        "https://bolid.ru/production/c2000-ip/",
    ])

    # 5. Another normal device row
    ws.append([
        "С2000-КДЛ",
        "Контроллер двухпроводной линии связи",
        "010001",
        "110-000-100",
        "В наличии",
        "16521.88",
        "15257.74",
        "https://bolid.ru/production/c2000-kdl/",
    ])

    out_path = HERE / "bolid_sample.xlsx"
    wb.save(str(out_path))
    print(f"Written: {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
