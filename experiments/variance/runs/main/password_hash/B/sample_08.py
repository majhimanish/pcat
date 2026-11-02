import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimum: N=2**17, r=8, p=1)
_N = 2 ** 17
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a password for storage at signup. Returns a self-describing string."""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
        maxmem=256 * 1024 * 1024,
    )
    return "scrypt${}${}${}${}${}".format(
        _N,
        _R,
        _P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a login attempt against the stored hash (constant-time compare)."""
    try:
        scheme, n, r, p, salt_b64, dk_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=256 * 1024 * 1024,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)
