"""Tests for config.mail_provider_configured (Flask and CTFd are stubbed)."""
import sys
import types


def stub(name, **attrs):
    """Register a fake module (and its parents) so impl.py imports without Flask or CTFd."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        mod_name = ".".join(parts[:i])
        sys.modules.setdefault(mod_name, types.ModuleType(mod_name))
        if i > 1:
            setattr(sys.modules[".".join(parts[: i - 1])], parts[i - 1], sys.modules[mod_name])
    for key, value in attrs.items():
        setattr(sys.modules[name], key, value)
    return sys.modules[name]


class Aborted(Exception):
    def __init__(self, code):
        self.code = code


def abort(code, description=None):
    raise Aborted(code)


REQUEST = types.SimpleNamespace(is_json=False, full_path="/page?x=1", method="GET", endpoint="views.page",
                                accept_mimetypes=types.SimpleNamespace(best="text/html"))

APP_CONFIG, STORED = {}, {}
stub("flask", current_app=types.SimpleNamespace(config=APP_CONFIG))
stub("CTFd.utils", get_config=lambda key: STORED.get(key))

from impl import mailgun  # noqa: E402


def test_not_configured():
    APP_CONFIG.clear(), STORED.clear()
    assert mailgun() is False
    APP_CONFIG["MAILGUN_API_KEY"] = "k"  # half a configuration is not enough
    assert mailgun() is False


def test_configured_in_app_config_or_admin_settings():
    APP_CONFIG.clear(), STORED.clear()
    APP_CONFIG.update(MAILGUN_API_KEY="k", MAILGUN_BASE_URL="https://api")
    assert mailgun() is True
    APP_CONFIG.clear()
    STORED.update(mailgun_api_key="k", mailgun_base_url="https://api")
    assert mailgun() is True
