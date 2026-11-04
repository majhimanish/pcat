"""Tests for integrations.help_page (Django and the app are stubbed)."""
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


stub("django.http", HttpRequest=object, HttpResponse=object)
stub("django.shortcuts", render=lambda request, tpl, ctx=None: (request, tpl, ctx))
stub("hc.front.decorators", require_setting=lambda key: (lambda f: f))

from impl import pd_help  # noqa: E402


def test_renders_help_template_with_channels_menu():
    req = object()
    assert pd_help(req) == (req, "add_pd_simple.html", {"page": "channels"})
