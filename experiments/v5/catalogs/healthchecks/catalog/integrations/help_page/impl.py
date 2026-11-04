from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from hc.front.decorators import require_setting


@require_setting("PD_ENABLED")
@require_setting("PD_APP_ID")
def pd_help(request: HttpRequest) -> HttpResponse:
    ctx = {"page": "channels"}
    return render(request, "add_pd_simple.html", ctx)
