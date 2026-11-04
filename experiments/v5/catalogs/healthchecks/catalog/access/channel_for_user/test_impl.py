"""Tests for access.channel_for_user (Django and the app are stubbed)."""
import pytest

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



class Http404(Exception):
    pass


class PermissionDenied(Exception):
    pass


class Owner:
    pass


class Project:
    def __init__(self, owner_id):
        self.owner_id = owner_id


class Channel:
    def __init__(self, code, project):
        self.code, self.project = code, project


class Membership:
    def __init__(self, is_rw):
        self.is_rw = is_rw


CHANNELS = {"c1": Channel("c1", Project(owner_id=1))}
MEMBERS = {(2, "c1"): Membership(True), (3, "c1"): Membership(False)}


class Query:
    def select_related(self, *names):
        return self


class ChannelModel:
    objects = Query()


class MemberModel:
    pass


def get_object_or_404(model, **kw):
    if model is MemberModel:
        key = (kw["user"].id, next(c for c, ch in CHANNELS.items() if ch.project is kw["project"]))
        if key not in MEMBERS:
            raise Http404
        return MEMBERS[key]
    if kw["code"] not in CHANNELS:
        raise Http404
    return CHANNELS[kw["code"]]


stub("django.core.exceptions", PermissionDenied=PermissionDenied)
stub("django.http", HttpRequest=object)
stub("django.shortcuts", get_object_or_404=get_object_or_404)
stub("hc.accounts.models", Member=MemberModel)
stub("hc.api.models", Channel=ChannelModel)

from impl import _get_channel_for_user, _get_rw_channel_for_user  # noqa: E402


class User:
    def __init__(self, uid, superuser=False):
        self.id, self.is_superuser, self.is_authenticated = uid, superuser, True


class Request:
    def __init__(self, user):
        self.user = user


@pytest.mark.parametrize("user,rw", [(User(9, superuser=True), True), (User(1), True), (User(2), True), (User(3), False)])
def test_access_levels(user, rw):
    channel, got_rw = _get_channel_for_user(Request(user), "c1")
    assert channel is CHANNELS["c1"] and got_rw is rw


def test_non_member_and_unknown_code_get_404():
    with pytest.raises(Http404):
        _get_channel_for_user(Request(User(4)), "c1")
    with pytest.raises(Http404):
        _get_channel_for_user(Request(User(1)), "nope")


def test_rw_variant_rejects_read_only_members():
    assert _get_rw_channel_for_user(Request(User(2)), "c1") is CHANNELS["c1"]
    with pytest.raises(PermissionDenied):
        _get_rw_channel_for_user(Request(User(3)), "c1")
