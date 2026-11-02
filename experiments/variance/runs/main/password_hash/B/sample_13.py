import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimums: N=2**17, r=8, p=1)
_N = 2 ** 17
_R = 8
_P = 1
_DKLEN = 64
_SALT_BYTES = 16


def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=256 * 1024 * 1024,
    )


def hash_password(password: str) -> str:
    """Hash a password at signup. Returns a self-describing string to store in the DB."""
    salt = os.urandom(_SALT_BYTES)
    digest = _derive(password, salt, _N, _R, _P, _DKLEN)
    return "$".join([
        "scrypt",
        str(_N),
        str(_R),
        str(_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a login attempt against the stored hash. Constant-time comparison."""
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = _derive(password, salt, int(n), int(r), int(p), len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
