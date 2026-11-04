def registered_only(f):
    """
    Decorator that requires the user to have a registered account
    :param f:
    :return:
    """

    @functools.wraps(f)
    def _registered_only(*args, **kwargs):
        if authed():
            return f(*args, **kwargs)
        else:
            if request.is_json or request.accept_mimetypes.best == "text/event-stream":
                abort(403)
            else:
                return redirect(url_for("auth.register", next=request.full_path))

    return _registered_only
