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
    """Return a salted scrypt hash string for the given plaintext password."""
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=128 * 1024 * 1024,
        dklen=_KEY_BYTES,
    )
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(key).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a plaintext password against a hash produced by hash_password."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(key_b64)
        n, r, p = int(n), int(r), int(p)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=128 * 1024 * 1024,
            dklen=len(expected),
        )
    except (ValueError, TypeError, AttributeError):
        return False
    return hmac.compare_digest(candidate, expected)
