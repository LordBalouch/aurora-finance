"""Parsing and cleaning of bank-export values. Pure functions, no Django."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d.%m.%y")

_SPACES = re.compile(r"[\s  ]+")


def parse_amount(text: str | None) -> Decimal | None:
    """'1 234,56' / '-1.234,56' / '1234.56' / '−50' / 'kr 50,00' -> Decimal. Blank -> None."""
    if text is None:
        return None
    s = _SPACES.sub("", str(text)).replace("−", "-").replace("kr", "").replace("NOK", "")
    if s in ("", "-"):
        return None
    if "," in s and "." in s:
        # The separator that comes last is the decimal one.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Not an amount: {text!r}") from exc


def parse_date(text: str) -> date:
    s = str(text).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Not a date: {text!r}")


# Noise that banks add around the merchant name. Order matters: longer phrases first.
_NOISE = [
    r"\bVISA\s+VAREKJ[ØO]P\b",
    r"\bVAREKJ[ØO]P\b",
    r"\bVISA\s+\d{4,}\b",  # Visa reference number
    r"\bVISA\b",
    r"\bBANKAXEPT\b",
    r"\bKORTKJ[ØO]P\b",
    r"\bNOTANR\s*\S+",
    r"\bKURS:?\s*[\d.,]+",
    r"\bDATO\s*\d{1,2}\.\d{1,2}(\.\d{2,4})?",
    r"\b\d{1,2}\.\d{1,2}(\.\d{2,4})?\b",  # dates inside the text
    r"\*+\d{2,}",  # masked card numbers like *1234
    r"\b(?:NOK|EUR|USD|SEK|DKK|GBP)\s*[\d.,]+",  # original currency amount
    r"VALUTAKURS:?\s*[\d.,]+",  # often glued to the word before
    r"\bKL\.?\s*\d{1,2}[:.]\d{2}",
]
_NOISE_RE = re.compile("|".join(_NOISE), re.IGNORECASE)


def clean_description(text: str) -> str:
    """'VISA VAREKJØP *1234 21.11 REMA 1000 STORO Kurs: 1.0000' -> 'REMA 1000 STORO'."""
    s = _NOISE_RE.sub(" ", str(text))
    s = _SPACES.sub(" ", s).strip(" -,.:;/")
    return s or str(text).strip()
