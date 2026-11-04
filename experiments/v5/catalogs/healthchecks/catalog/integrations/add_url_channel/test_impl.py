"""Tests for integrations.add_url_channel (Django and the app are stubbed: they are not installed)."""
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


CALLS = []


class Channel:
    def __init__(self, project, kind):
        self.project, self.kind, self.value, self.saved, self.assigned = project, kind, None, False, False
        CALLS.append(self)

    def save(self):
        self.saved = True

    def assign_all_checks(self):
        self.assigned = True


class AddUrlForm:
    def __init__(self, data=None):
        self.data = data or {}
        self.cleaned_data = {"value": self.data.get("value")}

    def is_valid(self):
        return bool(self.data.get("value", "").startswith("https://"))


class Project:
    code = "p-code"


LOOKUPS = []


def _get_rw_project_for_user(request, code):
    LOOKUPS.append((request, code))
    return Project()


stub("django.contrib.auth.decorators", login_required=lambda f: f)
stub("django.http", HttpResponse=object)
stub("django.shortcuts", redirect=lambda name, *a: ("redirect", name, a),
     render=lambda request, tpl, ctx=None: ("render", tpl, ctx))
stub("hc.accounts.http", AuthenticatedHttpRequest=object)
stub("hc.api.models", Channel=Channel)
stub("hc.front.forms", AddUrlForm=AddUrlForm)
stub("hc.front.decorators", require_setting=lambda key: (lambda f: f))
stub("hc.front.views", _get_rw_project_for_user=_get_rw_project_for_user)

from impl import add_msteams  # noqa: E402


class Request:
    def __init__(self, method, post=None):
        self.method, self.POST = method, post or {}


def test_get_renders_the_form_after_checking_project_access():
    kind, tpl, ctx = add_msteams(Request("GET"), "code-1")
    assert (kind, tpl) == ("render", "add_msteams.html") and isinstance(ctx["form"], AddUrlForm)
    assert LOOKUPS[-1][1] == "code-1" and ctx["page"] == "channels"


def test_valid_post_creates_assigns_and_redirects():
    CALLS.clear()
    result = add_msteams(Request("POST", {"value": "https://hooks.example/x"}), "code-1")
    assert result == ("redirect", "hc-channels", ("p-code",))
    [channel] = CALLS
    assert channel.kind == "msteamsw" and channel.value == "https://hooks.example/x"
    assert channel.saved and channel.assigned


def test_invalid_post_rerenders_without_creating():
    CALLS.clear()
    kind, tpl, ctx = add_msteams(Request("POST", {"value": "not a url"}), "code-1")
    assert kind == "render" and CALLS == []
