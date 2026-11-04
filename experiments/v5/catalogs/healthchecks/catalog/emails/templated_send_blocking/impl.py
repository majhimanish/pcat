from typing import Any
from hc.lib.emails import make_message, send


def report(to: str, ctx: dict[str, Any], headers: dict[str, str]) -> None:
    m = make_message("report", to, ctx, headers=headers)
    send(m, block=True)
