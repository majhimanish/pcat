def _allow_next_url(next_url: str | None) -> bool:
    if not next_url:
        return False

    # Allow redirects only to relative URLs
    return next_url.startswith("/") and not next_url.startswith("//")
