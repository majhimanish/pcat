"""Password hashing with stdlib PBKDF2-HMAC-SHA256; the iteration count is stored in the hash.

Standard library only. Format: pbkdf2_sha256$iterations$<salt b64>$<key b64>.
To raise the cost later, increase ITERATIONS: old hashes still verify, and
needs_rehash() tells you to re-hash them after the next successful login.
"""

import base64
import hashlib
import hmac
import os

ITERATIONS = 600000  # default for new hashes; raise over time
MIN_ITERATIONS = 600000  # OWASP 2023 minimum for PBKDF2-HMAC-SHA256; never hash below it
MAX_ITERATIONS = 10000000  # bounds the CPU a tampered stored hash can demand
SALT_BYTES = 16


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash of `password` for storage."""
    if not MIN_ITERATIONS <= iterations <= MAX_ITERATIONS:
        raise ValueError(f"iterations must be between {MIN_ITERATIONS} and {MAX_ITERATIONS}")
    salt = os.urandom(SALT_BYTES)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    b64 = base64.b64encode
    return f"pbkdf2_sha256${iterations}${b64(salt).decode()}${b64(key).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """True if `password` matches `stored`; False for a wrong or malformed hash.

    Hashes made with fewer iterations (e.g. before ITERATIONS was raised) still
    verify; use needs_rehash() to upgrade them.
    """
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


def needs_rehash(stored: str, iterations: int = ITERATIONS) -> bool:
    """True if `stored` should be replaced by hash_password(...) after a successful login."""
    try:
        scheme, stored_iterations, _, _ = stored.split("$")
        count = int(stored_iterations)
    except ValueError:
        return True
    return scheme != "pbkdf2_sha256" or not iterations <= count <= MAX_ITERATIONS
