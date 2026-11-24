from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from ai.ask import AIUnavailable, ask
from ai.providers import provider

EXAMPLES = [
    "How much did I spend on food this summer compared with last summer?",
    "Which subscriptions have become more expensive?",
    "When am I debt-free if I pay 3 000 kr extra a month?",
    "Where did most of my money go in the last three months?",
    "Was any month unusual lately?",
    "How much have I paid to Spotify in total?",
]


@require_http_methods(["GET", "POST"])
def ask_page(request):
    """Ask your data. GET shows the page; an HTMX POST answers one question."""
    if request.method == "GET":
        return render(
            request, "web/ask.html", {"examples": EXAMPLES, "local": provider() == "ollama"}
        )
    question = request.POST.get("question", "")
    context = {"question": question}
    try:
        context["answer"] = ask(question, refresh=request.POST.get("refresh") == "1")
    except AIUnavailable as exc:
        context["error"] = str(exc)
    return render(request, "web/_ask_answer.html", context)
