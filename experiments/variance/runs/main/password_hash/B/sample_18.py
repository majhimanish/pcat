import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimum: N=2**17, r=8, p=1)
_SCRYPT_N = 2 ** 17
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
_MAXMEM = 256 * 1024 * 1024


def hash_password(password: str) -> str:
    """Hash a password at signup. Returns a self-describing string to store in the DB."""
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_MAXMEM,
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
    """Check a login attempt against the stored hash. Constant-time comparison."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(key_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=_MAXMEM,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)
