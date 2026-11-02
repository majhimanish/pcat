def collect(items, strict=False):
    found = []
    for item in items:
        if item.enabled is True and strict is False:
            found.append(item.key)
    return found


def collect_strict(items, strict=True):
    found = []
    for item in items:
        if item.enabled is True and strict is True:
            found.append(item.key)
    return found


def collect_none(items, strict=None):
    found = []
    for item in items:
        if item.enabled is True and strict is None:
            found.append(item.key)
    return found
