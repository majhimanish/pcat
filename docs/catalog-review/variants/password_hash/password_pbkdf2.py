"""Password hashing with stdlib PBKDF2-HMAC-SHA256; iterations stored in the hash.

Standard library only. Format: pbkdf2_sha256$iterations$<salt b64>$<key b64>.
"""

import base64
import hashlib
import hmac
import os

ITERATIONS = 600000  # OWASP 2023 minimum for PBKDF2-HMAC-SHA256
MAX_ITERATIONS = 10000000  # bounds the CPU a (tampered) hash can demand
SALT_BYTES = 16


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash of `password` for storage."""
    salt = os.urandom(SALT_BYTES)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    b64 = base64.b64encode
    return f"pbkdf2_sha256${iterations}${b64(salt).decode()}${b64(key).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """True if `password` matches `stored`; False for a wrong or malformed hash."""
    try:
        scheme, iterations, salt_b64, key_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256" or not 0 < int(iterations) <= MAX_ITERATIONS:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(key_b64, validate=True)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                  int(iterations), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(key, expected)
