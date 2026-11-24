"""Desktop-app helpers: a ping so a second launch finds the running app, and Quit."""

import os
import threading

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

PING = "aurora"


def ping(request):
    return HttpResponse(PING, content_type="text/plain")


@require_POST
def quit_app(request):
    """Stop the desktop app's server shortly after this page is sent."""
    if not settings.DESKTOP:
        raise Http404
    threading.Timer(0.5, os._exit, args=[0]).start()
    return render(request, "web/quit.html")
