def authorize(f: ViewFunc) -> ViewFunc:
    @wraps(f)
    def wrapper(request: ApiRequest, *args: Any, **kwds: Any) -> HttpResponse:
        # For POST requests, we may need to look for the API key inside the
        # request body. Parse the body and put it in request.json
        # so views can avoid parsing it again.
        if request.method == "POST" and request.body:
            try:
                request.json = json.loads(request.body.decode())
            except ValueError:
                return error("could not parse request body")
            if not isinstance(request.json, dict):
                return error("json validation error: value is not an object")
        else:
            request.json = {}

        if "X-Api-Key" in request.headers:
            api_key = request.headers["X-Api-Key"]
        elif "api_key" in request.json:
            api_key = str(request.json["api_key"])
        else:
            api_key = ""

        if len(api_key) != 32:
            return error("missing api key", 401)

        project = Project.objects.for_api_key(api_key, accept_rw=True, accept_ro=False)
        if project is None:
            return error("wrong api key", 401)

        request.project = project
        request.readonly = False
        request.v = _get_api_version(request)
        return f(request, *args, **kwds)

    return wrapper
