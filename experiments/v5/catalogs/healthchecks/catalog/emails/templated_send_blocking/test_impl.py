"""Tests for emails.templated_send_blocking (hc.lib.emails is stubbed)."""
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


SENT = []
stub("hc.lib.emails", make_message=lambda name, to, ctx, headers=None: (name, to, ctx, headers),
     send=lambda message, block=False: SENT.append((message, block)))

from impl import report  # noqa: E402


def test_sends_with_headers_and_blocks():
    report("a@example.org", {"n": 1}, {"List-Unsubscribe": "<https://x>"})
    assert SENT == [(("report", "a@example.org", {"n": 1}, {"List-Unsubscribe": "<https://x>"}), True)]
