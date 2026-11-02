import base64
import hashlib
import hmac
import os

_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random per-user salt.

    Returns a self-describing string: scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=128 * _SCRYPT_N * _SCRYPT_R * 2,
    )
    return "$".join([
        "scrypt",
        str(_SCRYPT_N),
        str(_SCRYPT_R),
        str(_SCRYPT_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a login password against a stored hash from hash_password().

    Uses the parameters embedded in the stored hash and a constant-time
    comparison. Returns False for any malformed hash or mismatch.
    """
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)

        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=128 * n * r * 2,
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError, AttributeError):
        return False
