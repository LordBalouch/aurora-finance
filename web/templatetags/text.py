"""Safe rendering of the little markdown a model writes: paragraphs, '- ' lists, **bold**."""

import json
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline(line: str) -> str:
    return BOLD.sub(r"<strong>\1</strong>", escape(line))


@register.filter
def pretty_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, default=str)


@register.filter
def answer_html(text: str) -> str:
    """Everything is escaped first; only <p>, <ul>/<li> and <strong> are added."""
    out, items = [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for block in re.split(r"\n\s*\n", str(text or "").strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        para = []
        for line in lines:
            match = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)", line)
            if match:
                if para:
                    out.append("<p>" + "<br>".join(para) + "</p>")
                    para = []
                items.append(_inline(match.group(1)))
            else:
                flush()
                para.append(_inline(line))
        flush()
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
    return mark_safe("".join(out))
