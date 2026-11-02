import base64
import hashlib
import hmac
import os

_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a plaintext password using scrypt with a random salt.

    Returns a self-describing string: scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(password, str):
        raise TypeError("password must be a str")
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=128 * _SCRYPT_N * _SCRYPT_R * 2,
        dklen=_KEY_BYTES,
    )
    return "$".join([
        "scrypt",
        str(_SCRYPT_N),
        str(_SCRYPT_R),
        str(_SCRYPT_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(key).decode("ascii"),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a hash from hash_password().

    Uses a constant-time comparison. Returns False for malformed hashes.
    """
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(key_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=128 * n * r * 2,
            dklen=len(expected),
        )
    except (ValueError, TypeError, AttributeError, OverflowError, MemoryError):
        return False
    return hmac.compare_digest(candidate, expected)
