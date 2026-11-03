"""Password hashing with stdlib scrypt; cost parameters are stored in the hash.

Standard library only. Format: scrypt$n$r$p$<salt b64>$<key b64>.
"""

import base64
import hashlib
import hmac
import os

SCRYPT_N = 131072  # 2**17, r=8, p=1: OWASP minimum for scrypt
SCRYPT_R = 8
SCRYPT_P = 1
MAXMEM = 268435456  # 256 MiB; bounds the memory a (tampered) hash can demand
SALT_BYTES = 16


def hash_password(password: str, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> str:
    """Return a salted scrypt hash of `password` for storage."""
    salt = os.urandom(SALT_BYTES)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                         maxmem=MAXMEM, dklen=32)
    b64 = base64.b64encode
    return f"scrypt${n}${r}${p}${b64(salt).decode()}${b64(key).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """True if `password` matches `stored`; False for a wrong or malformed hash."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != "scrypt" or int(p) > 16:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(key_b64, validate=True)
        key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r),
                             p=int(p), maxmem=MAXMEM, dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(key, expected)
