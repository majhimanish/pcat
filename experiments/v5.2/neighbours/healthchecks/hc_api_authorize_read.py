def authorize_metrics(f: ViewFunc) -> ViewFunc:
    @wraps(f)
    def wrapper(request: ApiRequest, *args: Any, **kwds: Any) -> HttpResponse:
        api_key = request.headers.get("X-Api-Key", "")

        project = Project.objects.filter(api_key_readonly=api_key).first()
        if project is None:
            return error("wrong api key", 401)

        request.project = project
        request.readonly = True
        request.v = _get_api_version(request)
        return f(request, *args, **kwds)

    return wrapper
