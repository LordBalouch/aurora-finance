from ai.providers import available, setup_hint


def ai(request):
    return {"ai_available": available(), "ai_hint": setup_hint()}
