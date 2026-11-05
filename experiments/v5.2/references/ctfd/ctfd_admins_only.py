def admins_only(f):
    """
    Decorator that requires the user to be authenticated and an admin
    :param f:
    :return:
    """

    @functools.wraps(f)
    def admins_only_wrapper(*args, **kwargs):
        if is_admin():
            return f(*args, **kwargs)
        else:
            if request.is_json:
                abort(403)
            else:
                return redirect(url_for("auth.login", next=request.full_path))

    return admins_only_wrapper
