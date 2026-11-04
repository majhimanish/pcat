import re


def is_valid_username(username: str) -> bool:
    username_regex = r"(?=[a-zA-Z0-9._]{2,20}$)(?!.*[_.]{2})[^_.].*[^_.]"
    return re.fullmatch(username_regex, username) is not None
