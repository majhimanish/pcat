from flask import current_app as app
from CTFd.utils import get_config


def mailgun():
    if app.config.get("MAILGUN_API_KEY") and app.config.get("MAILGUN_BASE_URL"):
        return True
    if get_config("mailgun_api_key") and get_config("mailgun_base_url"):
        return True
    return False
