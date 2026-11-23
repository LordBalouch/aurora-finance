from django import template

from insights.formatting import format_nok

register = template.Library()


@register.filter
def nok(value, decimals=0):
    """{{ amount|nok }} -> '12 346 kr'."""
    if value is None or value == "":
        return "—"
    return format_nok(value, decimals=int(decimals))
