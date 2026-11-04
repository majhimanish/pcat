import functools
from flask import abort, redirect, request, url_for
from CTFd.utils import get_config
from CTFd.utils import user as current_user


def require_verified_emails(f):
    """
    Decorator to restrict an endpoint to users with confirmed active email addresses
    :param f:
    :return:
    """

    @functools.wraps(f)
    def _require_verified_emails(*args, **kwargs):
        if get_config("verify_emails"):
            if current_user.authed():
                if (
                    current_user.is_admin() is False
                    and current_user.is_verified() is False
                ):  # User is not confirmed
                    if request.is_json:
                        abort(403)
                    else:
                        return redirect(url_for("auth.confirm"))
        return f(*args, **kwargs)

    return _require_verified_emails
