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
_MAXMEM = 256 * 1024 * 1024


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def hash_password(plain: str) -> str:
    """Hash a password using scrypt with a unique random salt.

    Returns a self-describing string:
    scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(plain, str):
        raise TypeError("password must be a str")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(
        plain.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_DKLEN,
        maxmem=_MAXMEM,
    )
    return f"scrypt${_N}${_R}${_P}${_b64e(salt)}${_b64e(dk)}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a stored hash in constant time.

    Returns False for any malformed or mismatched hash rather than raising.
    """
    try:
        if not isinstance(plain, str) or not isinstance(hashed, str):
            return False
        scheme, n, r, p, salt_b64, hash_b64 = hashed.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        # Guard against absurd parameters in untrusted/corrupted input (DoS)
        if not (2 ** 14 <= n <= 2 ** 20) or n & (n - 1) or not (1 <= r <= 32) or not (1 <= p <= 16):
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
        if not expected:
            return False
        dk = hashlib.scrypt(
            plain.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=_MAXMEM * 4,
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError, MemoryError):
        return False
