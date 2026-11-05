def api_authed_only(f):
    """
    Decorator that requires the user to be authenticated for API endpoints
    :param f:
    :return:
    """

    @functools.wraps(f)
    def api_authed_only_wrapper(*args, **kwargs):
        if request.headers.get("Authorization") or request.cookies.get("session"):
            return f(*args, **kwargs)
        else:
            abort(403)

    return api_authed_only_wrapper
