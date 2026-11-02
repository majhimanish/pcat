import base64
import hashlib
import hmac
import os

_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16


def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=128 * n * r * 2 + 1024 * 1024,
    )


def hash_password(password: str) -> str:
    """Hash a plaintext password using scrypt with a random per-password salt.

    Returns a self-describing string:
    scrypt$n$r$p$base64(salt)$base64(hash)
    """
    if not isinstance(password, str):
        raise TypeError("password must be a str")
    salt = os.urandom(_SALT_BYTES)
    digest = _derive(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _SCRYPT_DKLEN)
    return "$".join([
        "scrypt",
        str(_SCRYPT_N),
        str(_SCRYPT_R),
        str(_SCRYPT_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a hash from hash_password.

    Uses a constant-time comparison. Returns False for malformed hashes.
    """
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        actual = _derive(password, salt, n, r, p, len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
