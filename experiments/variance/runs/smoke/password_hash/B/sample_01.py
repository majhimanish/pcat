import base64
import hashlib
import hmac
import os

_ALGORITHM = "sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2-HMAC-SHA256 hash string for storage."""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode("utf-8"), salt, _ITERATIONS)
    return "pbkdf2_{}${}${}${}".format(
        _ALGORITHM,
        _ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a login password against a stored hash using constant-time comparison."""
    try:
        scheme, iterations, salt_b64, hash_b64 = stored_hash.split("$")
        if not scheme.startswith("pbkdf2_"):
            return False
        algorithm = scheme[len("pbkdf2_"):]
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac(
            algorithm, password.encode("utf-8"), salt, int(iterations), len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)
