def check_callback_url(url: str):
    u = urlparse(url)
    try:
        port = u.port
    except ValueError as exc:
        raise ValueError("Callback URL is not allowed.") from exc
    if (
        u.scheme not in {"http", "https"}
        or not u.hostname
        or u.username is not None
        or u.password is not None
    ):
        raise ValueError("Callback URL is not allowed.")

    host = u.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    origin = f"{u.scheme}://{host}"
    if port is not None:
        origin += f":{port}"

    if not settings.lnbits_callback_url_rules:
        # no rules, all valid callback urls are allowed
        return
    for rule in settings.lnbits_callback_url_rules:
        try:
            if re.fullmatch(rule, origin) is not None:
                return
        except re.error:
            logger.debug(f"Invalid regex rule: '{rule}'. ")
            continue
    raise ValueError(
        f"Callback URL origin '{origin}' is not allowed. "
        "Please check your admin settings."
    )
