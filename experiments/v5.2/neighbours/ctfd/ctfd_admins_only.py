def admins_only_api(f):
    """
    Decorator that requires an admin session for API endpoints
    :param f:
    :return:
    """

    @functools.wraps(f)
    def admins_only_api_wrapper(*args, **kwargs):
        if authed():
            return f(*args, **kwargs)
        else:
            abort(403)

    return admins_only_api_wrapper
