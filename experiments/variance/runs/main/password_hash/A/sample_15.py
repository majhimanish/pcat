import base64
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(password: str, iterations: int = _DEFAULT_ITERATIONS) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt.

    Returns a self-describing string: algorithm$iterations$salt$hash
    (salt and hash are base64-encoded).
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        (
            _ALGORITHM,
            str(iterations),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(dk).decode("ascii"),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash produced by hash_password.

    Uses a constant-time comparison. Returns False for malformed hashes.
    """
    try:
        algorithm, iterations_str, salt_b64, hash_b64 = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_str)
        if iterations <= 0:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, AttributeError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(actual, expected)
