from __future__ import annotations


import json


from collections.abc import Callable


from functools import wraps


from typing import Any


from django.http import HttpRequest, HttpResponse, JsonResponse


from hc.accounts.models import Project


from hc.lib.typealias import ViewFunc


class ApiRequest:
    ...


def error(msg: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": msg}, status=status)


def _get_api_version(request: HttpRequest) -> int:
    if request.path_info.startswith("/api/v3/"):
        return 3
    if request.path_info.startswith("/api/v2/"):
        return 2
    return 1


def authorize_read(*args, **kwargs):
    ...


def cors(*args, **kwargs):
    ...
