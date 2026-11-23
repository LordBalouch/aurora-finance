"""Chart specs for static/js/charts.js.

Views build a small spec here; the JS turns it into an ECharts option with the shared theme.
Values become floats only at this boundary (for display) — all math stays in Decimal/pandas.
"""

from collections.abc import Sequence
from decimal import Decimal

# Categorical slots, dark mode (dataviz reference palette, validated as an ordered set).
# Assign in this order; never cycle past 8 — fold extra series into "Other".
CATEGORICAL = [
    "#3987e5",  # blue
    "#d95926",  # orange
    "#199e70",  # aqua
    "#c98500",  # yellow
    "#d55181",  # magenta
    "#008300",  # green
    "#9085e9",  # violet
    "#e66767",  # red
]

KINDS = {"line", "bar", "spark"}

# Sequential ramp (one hue, dim -> bright on the dark surface) for magnitude.
SEQUENTIAL = ["#14233b", "#1d3f6e", "#2a62a8", "#3987e5", "#86b7f2"]


def _num(value):
    return float(value) if isinstance(value, Decimal) else value


def chart(
    kind: str,
    x: Sequence[str],
    series: dict[str, Sequence],
    *,
    area: bool = False,
    horizontal: bool = False,
    money: bool = True,
    colors: Sequence[str] | None = None,
    stack: bool = False,
    y_max: float | None = None,
    links: Sequence[Sequence[str | None]] | None = None,
) -> dict:
    """Build a chart spec. `series` maps series name -> values aligned with `x`."""
    if kind not in KINDS:
        raise ValueError(f"Unknown chart kind: {kind}")
    if len(series) > len(CATEGORICAL):
        raise ValueError("More than 8 series: fold the rest into 'Other'.")
    for name, values in series.items():
        if len(values) != len(x):
            raise ValueError(f"Series {name!r} has {len(values)} values, expected {len(x)}.")
    return {
        "kind": kind,
        "x": list(x),
        "series": [{"name": n, "data": [_num(v) for v in vals]} for n, vals in series.items()],
        "area": area,
        "horizontal": horizontal and kind == "bar",
        "money": money,
        "stack": stack and kind == "bar",
        "y_max": y_max,
        # links[series][point] -> URL opened on click (drill-down to transactions).
        "links": [list(row) for row in links] if links else None,
        "palette": list(colors or CATEGORICAL),
    }


def heatmap(x: Sequence[str], y: Sequence[str], values, *, money: bool = True) -> dict:
    """values[row][col] with rows = y, cols = x."""
    cells = [[xi, yi, _num(v)] for yi, row in enumerate(values) for xi, v in enumerate(row)]
    top = max((c[2] for c in cells), default=0)
    return {
        "kind": "heatmap", "x": list(x), "y": list(y), "cells": cells, "max": top,
        "money": money, "palette": SEQUENTIAL,
    }  # fmt: skip


def sankey(sources: dict, uses: dict, *, middle: str = "Money in") -> dict:
    """Sources -> one middle node -> uses. Both sides must sum to the same total."""
    nodes = [{"name": n, "side": "source"} for n in sources]
    nodes.append({"name": middle, "side": "middle"})
    nodes += [{"name": n, "side": "use"} for n in uses]
    links = [{"source": n, "target": middle, "value": _num(v)} for n, v in sources.items()]
    links += [{"source": middle, "target": n, "value": _num(v)} for n, v in uses.items()]
    return {"kind": "sankey", "nodes": nodes, "links": links, "money": True,
            "palette": list(CATEGORICAL)}  # fmt: skip
