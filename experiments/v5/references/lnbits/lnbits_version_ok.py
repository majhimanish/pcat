def is_lnbits_version_ok(
    min_lnbits_version: str | None, max_lnbits_version: str | None
) -> bool:
    if min_lnbits_version and (
        version_parse(min_lnbits_version) > version_parse(settings.version)
    ):
        return False
    if max_lnbits_version and (
        version_parse(max_lnbits_version) <= version_parse(settings.version)
    ):
        return False

    return True
