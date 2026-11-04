def _allow_redirect(redirect_url: str | None) -> bool:
    if not redirect_url:
        return False

    parsed = urlparse(redirect_url)
    if parsed.netloc:
        # Allow redirects only to relative URLs
        return False

    try:
        match = resolve(parsed.path)
    except Resolver404:
        return False

    return match.url_name in POST_LOGIN_ROUTES
