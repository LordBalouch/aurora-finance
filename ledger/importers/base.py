"""Reading bank exports into plain rows. No Django."""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


class ImportFileError(ValueError):
    """A file that cannot be imported, with a message fit for the user."""


@dataclass(frozen=True)
class ParsedRow:
    line: int  # line number in the file, for error messages
    date: date
    amount: Decimal
    description: str
    balance: Decimal | None = None


def decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFileError("Unknown text encoding (expected UTF-8 or Windows-1252).")


def _cell_text(value) -> str:
    """Excel cell -> the same kind of text a CSV export would have."""
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, float):
        return f"{Decimal(str(value)):.2f}"
    return str(value).strip()


def read_xlsx(data: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    try:
        sheet = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
    except Exception as exc:  # corrupt or password-protected workbook
        raise ImportFileError("Could not open the Excel file.") from exc
    return [[_cell_text(c) for c in row] for row in sheet.iter_rows(values_only=True)]


def read_table(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Return (header, rows) from CSV (delimiter sniffed) or Excel (.xlsx)."""
    if data[:2] == b"PK":  # .xlsx is a zip file
        rows = [r for r in read_xlsx(data) if any(c for c in r)]
        if not rows:
            raise ImportFileError("The file is empty.")
        header = rows[0]
        return header, [dict(zip(header, r, strict=False)) for r in rows[1:]]
    text = decode(data)
    if not text.strip():
        raise ImportFileError("The file is empty.")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    header = [h.strip() for h in rows[0]]
    body = [dict(zip(header, (c.strip() for c in r), strict=False)) for r in rows[1:]]
    return header, body
