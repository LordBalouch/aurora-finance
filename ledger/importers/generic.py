"""Column-based importers.

`GenericImporter` finds the columns by name and covers the common layouts: one signed
amount column, or separate in/out columns (DNB, Sbanken, Nordea, SpareBank 1, Handelsbanken,
Storebrand, Bank Norwegian, Revolut ...). `MappedImporter` uses columns the user picked once
for a bank we do not recognise ("teach a new bank").
"""

from ..normalize import parse_amount, parse_date
from .base import ImportFileError, ParsedRow

SYNONYMS = {
    "date": [
        "bokføringsdato", "bokført dato", "dato", "transaksjonsdato", "date", "booking date",
        "bookdate", "transactiondate", "completed date", "started date", "reskontrodato",
    ],
    "description": [
        "forklaring", "beskrivelse", "tekst", "description", "tittel", "text", "melding",
    ],
    "amount": ["beløp", "beløp i nok", "amount", "beløp nok", "sum"],
    "out": [
        "ut fra konto", "ut", "uttak", "belastet", "ut av konto", "out", "money out", "paid out",
    ],
    "in": ["inn på konto", "inn", "innskudd", "godskrevet", "in", "money in", "paid in"],
    "balance": ["saldo", "balance", "bokført saldo"],
}  # fmt: skip
FIELDS = ("date", "description", "amount", "in", "out", "balance")
# Pending card payments: no booking date yet, and they come back later as booked rows.
PENDING = {"reservert", "reserved", "pending", "ikke bokført"}


def _find(header: list[str]) -> dict[str, str]:
    lower = {h.lower().strip(): h for h in header}
    found = {}
    for field, names in SYNONYMS.items():
        for name in names:  # first synonym wins, so 'bokføringsdato' beats 'dato'
            if name in lower:
                found[field] = lower[name]
                break
    return found


def usable(cols: dict[str, str]) -> bool:
    has_amount = bool(cols.get("amount")) or bool(cols.get("in") and cols.get("out"))
    return bool(cols.get("date") and cols.get("description")) and has_amount


def parse_with(cols: dict[str, str], rows: list[dict[str, str]]) -> list[ParsedRow]:
    """Rows -> ParsedRow with the given column for each field. All bad lines are reported."""
    parsed, errors = [], []
    for line, row in enumerate(rows, start=2):
        try:
            when = (row.get(cols["date"]) or "").strip()
            if when.lower() in PENDING or (not when and not any(row.values())):
                continue
            if cols.get("amount"):
                amount = parse_amount(row.get(cols["amount"]))
            else:
                inn = parse_amount(row.get(cols["in"]))
                out = parse_amount(row.get(cols["out"]))
                amount = (abs(inn) if inn else 0) - (abs(out) if out else 0)
            if not amount:
                continue  # zero rows (reservations, info lines) carry no money
            parsed.append(
                ParsedRow(
                    line=line,
                    date=parse_date(when),
                    amount=amount,
                    description=(row.get(cols["description"]) or "").strip(),
                    balance=parse_amount(row.get(cols["balance"])) if cols.get("balance") else None,
                )
            )
        except (ValueError, KeyError) as exc:
            errors.append(f"line {line}: {exc}")
    if errors:
        shown = "; ".join(errors[:5])
        more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
        raise ImportFileError(f"{len(errors)} rows could not be read: {shown}{more}")
    return parsed


class GenericImporter:
    name = "generic"
    label = "Generic (columns by name)"

    def matches(self, header: list[str]) -> bool:
        return usable(_find(header))

    def parse(self, header: list[str], rows: list[dict[str, str]]) -> list[ParsedRow]:
        return parse_with(_find(header), rows)


class MappedImporter:
    """Columns chosen by the user for one bank's layout."""

    def __init__(self, name: str, columns: dict[str, str]):
        self.name = name[:50]
        self.label = f"{name} (your column choice)"
        self.columns = {k: v for k, v in columns.items() if k in FIELDS and v}

    def matches(self, header: list[str]) -> bool:
        return usable(self.columns) and set(self.columns.values()) <= set(header)

    def parse(self, header: list[str], rows: list[dict[str, str]]) -> list[ParsedRow]:
        if not self.matches(header):
            raise ImportFileError("The chosen columns are not all in this file.")
        return parse_with(self.columns, rows)
