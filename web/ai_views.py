from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_POST

from ai.advisor import AIUnavailable, advise

from .ai_cards import CARDS


@require_POST
def ask(request, card):
    """HTMX: AI summary and tips for one card. The numbers are computed here, never sent in."""
    builder = CARDS.get(card)
    if builder is None:
        raise Http404
    context = {"card": card}
    try:
        title, task, facts = builder(request.POST)
        context["advice"] = advise(
            card, title, facts, task, refresh=request.POST.get("refresh") == "1"
        )
    except AIUnavailable as exc:
        context["error"] = str(exc)
    except (IndexError, KeyError, ValueError):
        context["error"] = "Not enough data for this view yet."
    return render(request, "web/_ai_answer.html", context)
