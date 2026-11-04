def verify_email(to: str, ctx: dict[str, Any]) -> None:
    send(make_message("verify-email", to, ctx))
