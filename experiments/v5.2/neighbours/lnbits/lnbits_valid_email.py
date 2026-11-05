def is_valid_wallet_name(name: str) -> bool:
    name_regex = r"[A-Za-z0-9 ._-]{1,64}"
    return re.match(name_regex, name) is not None
