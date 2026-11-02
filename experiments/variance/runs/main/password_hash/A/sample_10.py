import base64
import hashlib
import hmac
import os

_ALGORITHM = "sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(password: str, iterations: int = _ITERATIONS) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt.

    Returns a string of the form: pbkdf2_sha256$iterations$salt_b64$hash_b64
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash produced by hash_password."""
    try:
        scheme, iterations_str, salt_b64, hash_b64 = stored_hash.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, AttributeError, TypeError):
        return False

    if not isinstance(password, str):
        return False

    candidate = hashlib.pbkdf2_hmac(
        _ALGORITHM, password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(candidate, expected)
