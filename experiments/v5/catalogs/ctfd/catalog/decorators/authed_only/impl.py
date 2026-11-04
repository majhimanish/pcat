import functools
from flask import abort, redirect, request, url_for
from CTFd.utils.user import authed


def authed_only(f):
    """
    Decorator that requires the user to be authenticated
    :param f:
    :return:
    """

    @functools.wraps(f)
    def authed_only_wrapper(*args, **kwargs):
        if authed():
            return f(*args, **kwargs)
        else:
            if request.is_json or request.accept_mimetypes.best == "text/event-stream":
                abort(403)
            else:
                return redirect(url_for("auth.login", next=request.full_path))

    return authed_only_wrapper
