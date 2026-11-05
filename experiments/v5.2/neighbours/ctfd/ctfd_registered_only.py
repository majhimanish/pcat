def members_only(f):
    """
    Decorator that requires the user to have an account
    :param f:
    :return:
    """

    @functools.wraps(f)
    def _members_only(*args, **kwargs):
        if request.cookies.get("session"):
            return f(*args, **kwargs)
        else:
            if request.is_json:
                abort(403)
            else:
                return redirect(url_for("auth.register", next=request.full_path))

    return _members_only
