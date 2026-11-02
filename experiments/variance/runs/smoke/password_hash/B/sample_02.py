import base64
import hashlib
import hmac
import os

_SCHEME = "scrypt"
_N = 2 ** 15       # CPU/memory cost
_R = 8             # block size
_P = 1             # parallelization
_DKLEN = 64        # derived key length in bytes
_SALT_LEN = 16     # per-password random salt (bytes)
_MAXMEM = 128 * 1024 * 1024


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def hash_password(plain: str) -> str:
    """Hash a password with scrypt and a unique random salt.

    Returns a self-describing string:
        scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(plain, str):
        raise TypeError("password must be a str")
    salt = os.urandom(_SALT_LEN)
    dk = hashlib.scrypt(
        plain.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        maxmem=_MAXMEM,
        dklen=_DKLEN,
    )
    return f"{_SCHEME}${_N}${_R}${_P}${_b64e(salt)}${_b64e(dk)}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a hash from hash_password().

    Uses the parameters stored in the hash and a constant-time comparison.
    Returns False for any malformed hash instead of raising.
    """
    try:
        if not isinstance(plain, str) or not isinstance(hashed, str):
            return False
        scheme, n, r, p, salt_b64, hash_b64 = hashed.split("$")
        if scheme != _SCHEME:
            return False
        n, r, p = int(n), int(r), int(p)
        # Guard against absurd parameters in untrusted/corrupted input (DoS).
        if not (2 ** 14 <= n <= 2 ** 20) or n & (n - 1) or not (1 <= r <= 32) or not (1 <= p <= 16):
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
        if not expected or len(salt) < 8:
            return False
        maxmem = max(_MAXMEM, 130 * n * r * p)
        dk = hashlib.scrypt(
            plain.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=maxmem,
            dklen=len(expected),
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError, MemoryError, OverflowError):
        return False
