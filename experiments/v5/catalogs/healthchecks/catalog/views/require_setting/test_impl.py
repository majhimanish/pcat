"""Tests for views.require_setting (Django is stubbed)."""
import sys
import types


def stub(name, **attrs):
    """Register a fake module (and its parents) so impl.py imports without Django or the app."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        mod_name = ".".join(parts[:i])
        sys.modules.setdefault(mod_name, types.ModuleType(mod_name))
        if i > 1:
            setattr(sys.modules[".".join(parts[: i - 1])], parts[i - 1], sys.modules[mod_name])
    for key, value in attrs.items():
        setattr(sys.modules[name], key, value)
    return sys.modules[name]



class HttpResponse:
    def __init__(self, status=200):
        self.status_code = status


settings = types.SimpleNamespace(FOO_ENABLED=True, BAR_ENABLED=False)
stub("django.conf", settings=settings)
stub("django.http", HttpRequest=object, HttpResponse=HttpResponse)
stub("hc.lib.typealias", ViewFunc=object)

from impl import require_setting  # noqa: E402


@require_setting("FOO_ENABLED")
def foo(request, x):
    return ("foo", x)


@require_setting("BAR_ENABLED")
def bar(request):
    return "bar"


def test_enabled_setting_calls_the_view():
    assert foo(object(), 3) == ("foo", 3) and foo.__name__ == "foo"


def test_disabled_setting_is_404():
    assert bar(object()).status_code == 404
