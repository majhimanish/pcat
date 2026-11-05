def check_webhook_url(url: str):
    if not url.startswith(("http://", "https://")):
        raise ValueError("Webhook URL is not allowed.")
    if not settings.lnbits_callback_url_rules:
        return
    for rule in settings.lnbits_callback_url_rules:
        if re.match(rule, url) is not None:
            return
    raise ValueError("Webhook URL is not allowed.")
