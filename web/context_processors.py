from ai.providers import available, setup_hint


def ai(request):
    from django.conf import settings

    return {"ai_available": available(), "ai_hint": setup_hint(), "desktop": settings.DESKTOP}
