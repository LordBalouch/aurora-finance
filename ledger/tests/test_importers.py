from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ledger.dedup import fingerprints
from ledger.importers import ImportFileError, detect, read_table

FIX = Path(__file__).parent / "fixtures"


def parse(name):
    header, rows = read_table((FIX / name).read_bytes())
    return detect(header).parse(header, rows)


def test_in_out_columns_give_signed_amounts_and_skip_zero_rows():
    rows = parse("in_out.csv")
    assert [r.amount for r in rows] == [
        Decimal("-312.40"),
        Decimal("52300.00"),
        Decimal("-45.00"),
        Decimal("-45.00"),
    ]
    assert rows[0].date == date(2026, 11, 21)


def test_signed_amount_column_with_mixed_number_formats():
    rows = parse("signed.csv")
    assert [r.amount for r in rows] == [Decimal("-1234.50"), Decimal("-89.90")]
    assert rows[0].balance == Decimal("10000.00")


def test_windows_1252_file_keeps_norwegian_letters():
    (row,) = parse("cp1252.csv")
    assert row.description == "Kjøp Bøker og Ærender"


def test_unknown_columns_are_rejected_with_the_header():
    header, _ = read_table(b"Foo;Bar\n1;2\n")
    with pytest.raises(ImportFileError, match="Foo, Bar"):
        detect(header)


def test_bad_rows_are_reported_with_line_numbers():
    header, rows = read_table(b"Dato;Tekst;Bel\xc3\xb8p\n32.13.2026;X;-1\n")
    with pytest.raises(ImportFileError, match="line 2"):
        detect(header).parse(header, rows)


def test_identical_same_day_rows_get_different_fingerprints():
    rows = parse("in_out.csv")
    prints = fingerprints(rows)
    assert len(set(prints)) == len(prints) == 4
    assert fingerprints(rows) == prints  # stable


def test_xlsx_with_real_dates_and_numbers():
    import io
    from datetime import datetime

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Dato", "Forklaring", "Rentedato", "Ut fra konto", "Inn på konto"])
    ws.append(
        [
            datetime(2026, 3, 5),
            "Varekjøp Kiwi 332 Dato 05.03 kl. 19.40",
            datetime(2026, 3, 6),
            72.58,
            None,
        ]
    )
    ws.append([datetime(2026, 3, 6), "Lønn Arbeidsgiver AS", datetime(2026, 3, 6), None, 20580.17])
    buf = io.BytesIO()
    wb.save(buf)
    header, rows = read_table(buf.getvalue())
    parsed = detect(header).parse(header, rows)
    assert [(r.date, r.amount) for r in parsed] == [
        (date(2026, 3, 5), Decimal("-72.58")),
        (date(2026, 3, 6), Decimal("20580.17")),
    ]
