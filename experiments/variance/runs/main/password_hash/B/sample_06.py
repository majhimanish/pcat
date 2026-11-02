import base64
import hashlib
import hmac
import os

_ALGORITHM = "sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random salt.

    Returns a self-describing string: pbkdf2_sha256$iterations$salt$hash
    """
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        _ALGORITHM, password.encode("utf-8"), salt, _ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        _ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a login password against a stored hash in constant time."""
    try:
        scheme, iterations, salt_b64, hash_b64 = stored_hash.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        _ALGORITHM, password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(candidate, expected)
