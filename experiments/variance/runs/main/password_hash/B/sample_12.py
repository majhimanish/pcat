import base64
import hashlib
import hmac
import os

_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16
_MAX_PASSWORD_BYTES = 1024


def _derive(password: bytes, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password,
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=128 * n * r * 2 + 1024 * 1024,
    )


def hash_password(plain: str) -> str:
    """Hash a password with scrypt and a random per-password salt.

    Returns a self-describing string:
    scrypt$N$r$p$base64(salt)$base64(hash)
    """
    if not isinstance(plain, str):
        raise TypeError("password must be a str")
    pw = plain.encode("utf-8")
    if len(pw) > _MAX_PASSWORD_BYTES:
        raise ValueError("password too long")

    salt = os.urandom(_SALT_BYTES)
    digest = _derive(pw, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _SCRYPT_DKLEN)
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a hash from hash_password (constant-time compare)."""
    try:
        if not isinstance(plain, str) or not isinstance(hashed, str):
            return False
        pw = plain.encode("utf-8")
        if len(pw) > _MAX_PASSWORD_BYTES:
            return False

        scheme, n, r, p, salt_b64, hash_b64 = hashed.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        # Guard against resource exhaustion from untrusted/tampered parameters.
        if not (2 ** 14 <= n <= 2 ** 20) or n & (n - 1) != 0:
            return False
        if not (1 <= r <= 32) or not (1 <= p <= 16):
            return False

        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        if not (8 <= len(salt) <= 64) or not (16 <= len(expected) <= 64):
            return False

        actual = _derive(pw, salt, n, r, p, len(expected))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False
