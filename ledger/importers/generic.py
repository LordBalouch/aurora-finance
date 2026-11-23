"""Finds the columns by name. Covers the common Norwegian layouts: one signed amount column,
or separate in/out columns. Bank-specific importers can override details later."""

from ..normalize import parse_amount, parse_date
from .base import ImportFileError, ParsedRow

SYNONYMS = {
    "date": ["bokføringsdato", "dato", "transaksjonsdato", "date", "booking date"],
    "description": ["forklaring", "beskrivelse", "tekst", "description", "tittel", "text"],
    "amount": ["beløp", "beløp i nok", "amount"],
    "out": ["ut fra konto", "ut", "uttak", "belastet"],
    "in": ["inn på konto", "inn", "innskudd", "godskrevet"],
    "balance": ["saldo", "balance", "bokført saldo"],
}


def _find(header: list[str]) -> dict[str, str]:
    lower = {h.lower().strip(): h for h in header}
    found = {}
    for field, names in SYNONYMS.items():
        for name in names:  # first synonym wins, so 'bokføringsdato' beats 'dato'
            if name in lower:
                found[field] = lower[name]
                break
    return found


class GenericImporter:
    name = "generic"
    label = "Generic (columns by name)"

    def matches(self, header: list[str]) -> bool:
        cols = _find(header)
        has_amount = "amount" in cols or ("in" in cols and "out" in cols)
        return {"date", "description"} <= cols.keys() and has_amount

    def parse(self, header: list[str], rows: list[dict[str, str]]) -> list[ParsedRow]:
        cols = _find(header)
        parsed, errors = [], []
        for line, row in enumerate(rows, start=2):
            try:
                if "amount" in cols:
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
                        date=parse_date(row[cols["date"]]),
                        amount=amount,
                        description=row.get(cols["description"], "").strip(),
                        balance=parse_amount(row.get(cols["balance"]))
                        if "balance" in cols
                        else None,
                    )
                )
            except (ValueError, KeyError) as exc:
                errors.append(f"line {line}: {exc}")
        if errors:
            shown = "; ".join(errors[:5])
            more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
            raise ImportFileError(f"{len(errors)} rows could not be read: {shown}{more}")
        return parsed
