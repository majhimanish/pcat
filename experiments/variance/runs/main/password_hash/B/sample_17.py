import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimum: N=2**17, r=8, p=1)
_N = 2 ** 17
_R = 8
_P = 1
_SALT_LEN = 16
_DKLEN = 32
_MAXMEM = 256 * 1024 * 1024


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=_MAXMEM,
    )


def hash_password(plain: str) -> str:
    """Hash a password using scrypt with a random per-password salt.

    Returns a self-describing string:
        scrypt$N$r$p$<b64 salt>$<b64 hash>
    """
    if not isinstance(plain, str):
        raise TypeError("password must be a str")
    salt = os.urandom(_SALT_LEN)
    digest = _scrypt(plain, salt, _N, _R, _P, _DKLEN)
    return "scrypt${}${}${}${}${}".format(
        _N,
        _R,
        _P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a hash from hash_password (constant-time compare)."""
    try:
        if not isinstance(plain, str) or not isinstance(hashed, str):
            return False
        scheme, n, r, p, salt_b64, hash_b64 = hashed.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        # Guard against absurd parameters in untrusted/corrupt hashes
        if n < 2 or n & (n - 1) or n > 2 ** 20 or r < 1 or r > 32 or p < 1 or p > 16:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        actual = _scrypt(plain, salt, n, r, p, len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
