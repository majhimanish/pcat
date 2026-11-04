from functools import wraps
from typing import Any
from django.http import HttpRequest, HttpResponse, JsonResponse
from hc.accounts.models import Project
from hc.api.decorators import ApiRequest
from hc.lib.typealias import ViewFunc


def error(msg: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": msg}, status=status)


def _get_api_version(request: HttpRequest) -> int:
    if request.path_info.startswith("/api/v3/"):
        return 3
    if request.path_info.startswith("/api/v2/"):
        return 2
    return 1


def authorize_read(f: ViewFunc) -> ViewFunc:
    @wraps(f)
    def wrapper(request: ApiRequest, *args: Any, **kwds: Any) -> HttpResponse:
        if "X-Api-Key" in request.headers:
            api_key = request.headers["X-Api-Key"]
        else:
            api_key = ""

        if len(api_key) != 32:
            return error("missing api key", 401)

        project = Project.objects.for_api_key(api_key, accept_rw=True, accept_ro=True)
        if project is None:
            return error("wrong api key", 401)

        request.project = project
        request.readonly = (
            api_key.startswith("hcr_") or api_key == request.project.api_key_readonly
        )
        request.v = _get_api_version(request)
        return f(request, *args, **kwds)

    return wrapper
