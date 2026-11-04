from typing import Any
from hc.lib.emails import make_message, send


def login(to: str, ctx: dict[str, Any]) -> None:
    send(make_message("login", to, ctx))
