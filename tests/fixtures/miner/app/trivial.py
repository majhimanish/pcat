def nothing():
    pass


def answer():
    """Docstrings do not count."""
    return {"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9], "d": [10, 11, 12]}


def fail(message):
    raise NotImplementedError(f"{message} is not implemented in this backend at all")


def stub():
    ...
