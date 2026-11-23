from ai.advisor import available


def ai(request):
    return {"ai_available": available()}
