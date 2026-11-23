"""Number formatting, Norwegian style. Pure functions, no Django."""

from decimal import ROUND_HALF_UP, Decimal

THIN_SPACE = " "  # narrow no-break space, as used by nb-NO grouping
MINUS = "−"


def format_nok(amount: Decimal | int, *, decimals: int = 0) -> str:
    """Format an amount as Norwegian kroner: 12345.6 -> '12 346 kr', -50 -> '−50 kr'."""
    value = Decimal(amount)
    quant = Decimal(1).scaleb(-decimals)
    rounded = value.quantize(quant, rounding=ROUND_HALF_UP)
    sign = MINUS if rounded < 0 else ""
    whole, _, frac = f"{abs(rounded):.{decimals}f}".partition(".")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    text = THIN_SPACE.join(groups)
    if frac:
        text += "," + frac
    return f"{sign}{text} kr"


def percent_change(current: Decimal, previous: Decimal) -> Decimal | None:
    """Relative change in percent, or None when there is no base to compare with."""
    if previous == 0:
        return None
    return (Decimal(current) - Decimal(previous)) / abs(Decimal(previous)) * 100
