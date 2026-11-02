import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimums: N=2^17, r=8, p=1)
_SCRYPT_N = 2 ** 17
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16
_MAXMEM = 256 * 1024 * 1024


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def hash_password(password: str) -> str:
    """Hash a password at signup. Returns a self-describing string to store in the DB."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_MAXMEM,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a login attempt against the stored hash. Constant-time comparison."""
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(digest_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)
