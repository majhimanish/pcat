def authorize_ping_key(f: ViewFunc) -> ViewFunc:
    @wraps(f)
    def wrapper(request: ApiRequest, *args: Any, **kwds: Any) -> HttpResponse:
        ping_key = request.headers.get("X-Ping-Key", "")

        project = Project.objects.filter(ping_key=ping_key).first()
        if project is None:
            return error("wrong ping key", 401)

        request.project = project
        request.readonly = False
        request.v = _get_api_version(request)
        return f(request, *args, **kwds)

    return wrapper
