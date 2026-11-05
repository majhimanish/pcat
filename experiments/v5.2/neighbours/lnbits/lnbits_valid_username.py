def is_valid_tag(tag: str) -> bool:
    tag_regex = r"[a-z0-9][a-z0-9-]{0,31}"
    return re.search(tag_regex, tag) is not None
