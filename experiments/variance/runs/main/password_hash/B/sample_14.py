import base64
import hashlib
import hmac
import os

# scrypt parameters (OWASP-recommended minimums or better)
_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt.

    Returns a self-describing string: scrypt$N$r$p$salt_b64$hash_b64
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=128 * _SCRYPT_N * _SCRYPT_R * 2,
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
    """Verify a password against a stored hash in constant time."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(key_b64)

        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=128 * n * r * 2,
            dklen=len(expected),
        )
    except (ValueError, TypeError, AttributeError):
        return False

    return hmac.compare_digest(candidate, expected)
