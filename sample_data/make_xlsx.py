#!/usr/bin/env python3
"""Generate demo_import_products.xlsx from the CSV (requires openpyxl).

Usage:  python make_xlsx.py
"""
import csv
import os

from openpyxl import Workbook

HERE = os.path.dirname(os.path.abspath(__file__))

def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "APH DEMO DATA"
    with open(os.path.join(HERE, "demo_import_products.csv"), encoding="utf-8") as fh:
        for row in csv.reader(fh):
            ws.append(row)
    out = os.path.join(HERE, "demo_import_products.xlsx")
    wb.save(out)
    print(f"wrote {out}")

if __name__ == "__main__":
    main()
